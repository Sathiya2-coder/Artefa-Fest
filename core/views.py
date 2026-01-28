from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password, check_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Event, Registration, Schedule, ContactMessage, Coordinator, Team, TeamMember, ChatbotTraining
from .forms import RegistrationForm, ContactForm, LoginForm, ForgotPasswordForm, EventForm, CoordinatorForm, SendAlertForm
from .chatbot import chatbot
import json
import logging
import csv
import uuid
import traceback
import os

# Configure logger for this module
logger = logging.getLogger(__name__)

# ============ VALIDATION HELPER FUNCTIONS ============
def validate_event_registration_limit(register_number, new_event=None, exclude_registration_id=None):
    """
    Validate that a register number doesn't exceed event type limits.
    Each register number can register for:
    - ONE technical event
    - ONE non-technical event
    - NOT two or more of same type
    - Cannot be team lead of one event AND member of another event of same type
    
    Args:
        register_number: The registration number to check
        new_event: The new event trying to register (Event object)
        exclude_registration_id: Registration ID to exclude from check (for edits)
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Get all registrations for this register number
        query = Registration.objects.filter(register_number__iexact=register_number)
        
        if exclude_registration_id:
            query = query.exclude(id=exclude_registration_id)
        
        registrations = list(query.select_related('event'))
        
        # Count by event type and check team lead status
        technical_registrations = [reg for reg in registrations if reg.event.event_type == 'technical']
        non_technical_registrations = [reg for reg in registrations if reg.event.event_type == 'non-technical']
        
        technical_count = len(technical_registrations)
        non_technical_count = len(non_technical_registrations)
        
        # Check if person is team lead of any technical event
        is_team_lead_technical = any(reg.is_team_lead for reg in technical_registrations)
        is_team_lead_non_technical = any(reg.is_team_lead for reg in non_technical_registrations)
        
        # If new event is being added, check if it would exceed limit
        if new_event:
            if new_event.event_type == 'technical':
                # Cannot add if already registered for 1+ technical events
                if technical_count >= 1:
                    return False, f'❌ Register number "{register_number}" is already registered for one technical event. Cannot register for another technical event.'
                # Cannot be member of another technical if already team lead of any technical
                if is_team_lead_technical:
                    return False, f'❌ Register number "{register_number}" is already team lead of a technical event. Cannot register as member of another technical event.'
            
            elif new_event.event_type == 'non-technical':
                # Cannot add if already registered for 1+ non-technical events
                if non_technical_count >= 1:
                    return False, f'❌ Register number "{register_number}" is already registered for one non-technical event. Cannot register for another non-technical event.'
                # Cannot be member of another non-technical if already team lead of any non-technical
                if is_team_lead_non_technical:
                    return False, f'❌ Register number "{register_number}" is already team lead of a non-technical event. Cannot register as member of another non-technical event.'
        
        return True, None
    
    except Exception as e:
        logger.error(f"Error in validate_event_registration_limit: {e}")
        return False, f"Error validating registration: {str(e)}"

def intro(request):
    """Splash screen with NEC logo loading animation"""
    return render(request, 'core/intro.html')

def home(request):
    # Get all events
    events = Event.objects.all()
    total_events = events.count()
    
    # Get all schedule items grouped by date
    schedule_items = Schedule.objects.all().order_by('date', 'start_time', 'order')
    
    # Group schedule by date
    schedule_by_date = {}
    for item in schedule_items:
        date_str = item.date.strftime('%Y-%m-%d')
        if date_str not in schedule_by_date:
            schedule_by_date[date_str] = []
        schedule_by_date[date_str].append(item)
    
    context = {
        'events': events,
        'schedule_items': schedule_items,
        'schedule_by_date': schedule_by_date,
        'total_events': total_events,
    }
    return render(request, 'core/home.html', context)

def about(request):
    technical_events = Event.objects.filter(event_type='technical').prefetch_related('coordinators', 'registration_set')
    nontechnical_events = Event.objects.filter(event_type='non-technical').prefetch_related('coordinators', 'registration_set')
    
    context = {
        'technical_events': technical_events,
        'nontechnical_events': nontechnical_events,
    }
    return render(request, 'core/about.html', context)

def events(request):
    events = Event.objects.all()
    context = {
        'all_events': events,
    }
    return render(request, 'core/events.html', context)

def schedule(request):
    schedule_items = Schedule.objects.all()
    
    # Group schedule by date
    schedule_by_date = {}
    for item in schedule_items:
        date_str = item.date.strftime('%Y-%m-%d')
        if date_str not in schedule_by_date:
            schedule_by_date[date_str] = []
        schedule_by_date[date_str].append(item)
    
    context = {
        'schedule_by_date': schedule_by_date,
    }
    return render(request, 'core/schedule.html', context)


def register(request):
    """
    Handle user registration for events, including team registration.
    """
    import logging
    import json
    from django.db import IntegrityError, transaction
    from django.contrib.auth.models import User
    from django.contrib.auth import login
    from django.contrib.auth.hashers import make_password
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from core.models import Registration, Event, Team, TeamMember
    from core.forms import RegistrationForm
    import traceback
    
    logger = logging.getLogger(__name__)
    
    def parse_team_members(team_members_str):
        """Parse team members JSON string."""
        if not team_members_str or not team_members_str.strip():
            return []
        
        team_members_str = team_members_str.strip()
        logger.info(f"Team members string received: {team_members_str}")
        
        try:
            members_data = json.loads(team_members_str)
            logger.info(f"Successfully parsed as JSON: {type(members_data)}")
            
            if isinstance(members_data, list):
                return members_data
            elif isinstance(members_data, dict):
                return [members_data]
            else:
                logger.error(f"Unexpected JSON structure: {type(members_data)}")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            # Try alternative parsing - remove single quotes and parse manually
            try:
                cleaned_str = team_members_str.replace("'", '"')
                members_data = json.loads(cleaned_str)
                if isinstance(members_data, list):
                    return members_data
                elif isinstance(members_data, dict):
                    return [members_data]
                else:
                    return []
            except:
                logger.error(f"Failed to parse even after cleaning")
                return []
        except Exception as e:
            logger.error(f"Error parsing team members: {e}")
            return []
    
    def map_year(year_str):
        """Map year string to choice value."""
        year_str = str(year_str).strip().lower()
        
        if '2nd' in year_str or year_str == '2':
            return '2'
        elif '3rd' in year_str or year_str == '3':
            return '3'
        elif '4th' in year_str or year_str == '4':
            return '4'
        else:
            return '1'  # Default to 1st Year
    
    def map_department(dept_str):
        """Map department string to choice value."""
        dept_str = str(dept_str).strip().upper()
        
        if 'CSE' in dept_str:
            return 'CSE'
        elif 'ECE' in dept_str:
            return 'ECE'
        elif 'MECH' in dept_str:
            return 'MECH'
        elif 'CIVIL' in dept_str:
            return 'CIVIL'
        elif 'AIDS' in dept_str or 'AI' in dept_str:
            return 'AIDS'
        else:
            return 'AIDS'  # Default to AIDS
    
    def create_or_get_user(username, email, password=None):
        """Create or get existing user."""
        try:
            if password:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                logger.info(f"New user created: {user.id}")
            else:
                user = User.objects.get(username__iexact=username)
                logger.info(f"Existing user retrieved: {user.id}")
            return user, True  # True indicates success
        except IntegrityError:
            # User already exists
            try:
                user = User.objects.get(username__iexact=username)
                logger.info(f"User already exists, retrieved: {user.id}")
                return user, True
            except User.DoesNotExist:
                logger.error(f"IntegrityError but user doesn't exist: {username}")
                return None, False
        except Exception as e:
            logger.error(f"Error creating/getting user {username}: {e}")
            return None, False
    
    def process_team_members(team, selected_event, team_members_data, registration, team_name_input, hashed_password):
        """Process and add team members to TeamMember table."""
        added_members = []
        already_in_team = []
        skipped_members = []
        
        if not team_members_data or len(team_members_data) == 0:
            logger.info("No team members data to process")
            return added_members, already_in_team, skipped_members
        
        logger.info(f"Processing {len(team_members_data)} team members for TeamMember table")
        members_count = len(team_members_data)
        
        for idx, member_data in enumerate(team_members_data, 1):
            if not isinstance(member_data, dict):
                skipped_members.append(f"Invalid data format at index {idx}")
                continue
            
            # Extract data with proper field names
            member_reg = member_data.get('register_number', '').strip().upper()
            member_name = member_data.get('full_name', '').strip()
            member_email = member_data.get('email', '').strip()
            member_phone = member_data.get('phone', '').strip() or member_data.get('phone_number', '').strip()
            
            logger.info(f"[{idx}/{members_count}] Processing team member: {member_reg} - {member_name}")
            
            # Validate member data
            if not member_reg:
                skipped_members.append(f"Member {idx}: Empty register number")
                continue
                
            if member_reg == registration.register_number.upper():
                skipped_members.append(f"Member {idx}: Duplicate of team lead")
                continue
            
            try:
                # ✅ VALIDATE EVENT REGISTRATION LIMITS for the member
                is_valid, error_msg = validate_event_registration_limit(member_reg, selected_event)
                if not is_valid:
                    logger.warning(f"[{idx}/{members_count}] Event registration limit validation failed for member {member_reg}: {error_msg}")
                    skipped_members.append(f"Member {member_reg}: {error_msg}")
                    continue
                
                # Check if member already exists
                existing_member_reg = None
                try:
                    existing_member_reg = Registration.objects.get(
                        register_number__iexact=member_reg,
                        event=selected_event
                    )
                    logger.info(f"[{idx}/{members_count}] Found existing registration for: {member_reg}")
                    
                    # Check if member is already in ANY team
                    if existing_member_reg.team and existing_member_reg.team != team:
                        warning_msg = f"Member {member_reg} is already in team '{existing_member_reg.team.name}'"
                        skipped_members.append(warning_msg)
                        continue
                        
                except Registration.DoesNotExist:
                    # Create new registration for team member
                    logger.info(f"[{idx}/{members_count}] Creating new registration for: {member_reg}")
                    
                    # Map year and department
                    year_choice = map_year(member_data.get('year', ''))
                    dept_choice = map_department(member_data.get('department', ''))
                    
                    # Create Registration for team member
                    existing_member_reg = Registration.objects.create(
                        full_name=member_name if member_name else f"Team Member {idx}",
                        register_number=member_reg,
                        email=member_email if member_email else f"{member_reg}@example.com",
                        phone_number=member_phone if member_phone else "0000000000",
                        year=year_choice,
                        department=dept_choice,
                        event=selected_event,
                        team=team,
                        team_name=team_name_input,
                        team_password=hashed_password,
                    )
                    logger.info(f"[{idx}/{members_count}] Created registration: {existing_member_reg.id} - {member_reg}")
                
                # Check if member is already in this team
                if TeamMember.objects.filter(team=team, registration=existing_member_reg).exists():
                    already_in_team.append(member_reg)
                    logger.warning(f"[{idx}/{members_count}] Member already in TeamMember table: {member_reg}")
                else:
                    # Add to TeamMember table
                    team_member = TeamMember.objects.create(
                        team=team,
                        registration=existing_member_reg,
                        status='pending'
                    )
                    added_members.append({
                        'reg_no': member_reg,
                        'name': existing_member_reg.full_name
                    })
                    logger.info(f"[{idx}/{members_count}] Added to TeamMember table (ID: {team_member.id})")
                    
                    # Update Registration if needed
                    if existing_member_reg.team != team:
                        existing_member_reg.team = team
                        existing_member_reg.team_name = team_name_input
                        existing_member_reg.save()
                        logger.info(f"[{idx}/{members_count}] Updated Registration.team for: {member_reg}")
            
            except Exception as e:
                error_msg = f"Error processing {member_reg}: {str(e)}"
                logger.error(f"[{idx}/{members_count}] {error_msg}")
                logger.error(traceback.format_exc())
                skipped_members.append(error_msg)
        
        return added_members, already_in_team, skipped_members
    
    def create_success_message(team_name_input, registration, team_password, added_members, skipped_members):
        """Create success message for registration."""
        if team_name_input:
            success_msg = f'Registration successful! Team "{team_name_input}" created.\n'
            success_msg += f'Team Leader: {registration.full_name} ({registration.register_number})\n'
            success_msg += f'Team Password: {team_password}\n'
            
            if added_members:
                success_msg += f'\nTeam members added ({len(added_members)}):\n'
                for member in added_members:
                    success_msg += f'  • {member["name"]} ({member["reg_no"]}) - Pending join\n'
            
            if skipped_members:
                success_msg += f'\nSkipped ({len(skipped_members)} members):\n'
                for skipped in skipped_members[:5]:
                    success_msg += f'  • {skipped}\n'
                if len(skipped_members) > 5:
                    success_msg += f'  • ... and {len(skipped_members) - 5} more\n'
        else:
            success_msg = f'Registration successful! You are now registered for {registration.event.name}.'
        
        return success_msg
    
    # Main registration logic starts here
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        logger.info(f"Form submitted with data: {request.POST.dict()}")
        
        if form.is_valid():
            logger.info("Form is valid, proceeding with registration")
            try:
                # Check if participant already exists
                register_number = form.cleaned_data.get('register_number', '').strip()
                email = form.cleaned_data.get('email', '').strip()
                
                logger.info(f"Checking registration for: {register_number}, {email}")
                
                # Get selected event to check event type
                selected_event = form.cleaned_data.get('events')
                if not selected_event:
                    raise ValueError("Event selection is required")
                
                # Check if this is a NEW registration or updating existing
                existing_reg_for_same_event = Registration.objects.filter(
                    register_number__iexact=register_number,
                    event=selected_event
                ).exists()
                
                if existing_reg_for_same_event:
                    logger.warning(f"Registration number {register_number} already registered for event {selected_event.name}")
                    form.add_error('register_number', f'Registration number "{register_number}" is already registered for this event.')
                    return render(request, 'core/register.html', {'form': form})
                
                # Create or get user
                password = form.cleaned_data.get('password')
                user, user_created = create_or_get_user(register_number, email, password)
                
                if not user:
                    messages.error(request, 'Error creating user account. Please try again.')
                    return render(request, 'core/register.html', {'form': form})
                
                logger.info(f"User {'created' if user_created else 'retrieved'}: {user.id}")
                
                # Now do the rest inside atomic block
                with transaction.atomic():
                    # Event already validated above
                    logger.info(f"Event selected: {selected_event.name if selected_event else 'None'}")
                    
                    # ✅ VALIDATE EVENT REGISTRATION LIMITS
                    is_valid, error_msg = validate_event_registration_limit(register_number, selected_event)
                    if not is_valid:
                        logger.warning(f"Event registration limit validation failed: {error_msg}")
                        messages.error(request, error_msg)
                        return render(request, 'core/register.html', {'form': form})
                    
                    # Create registration
                    registration = form.save(commit=False)
                    registration.user = user
                    registration.event = selected_event
                    
                    # Get team name if provided
                    team_name_input = form.cleaned_data.get('team_name', '').strip()
                    if team_name_input:
                        registration.team_name = team_name_input
                    
                    # Save registration
                    registration.save()
                    logger.info(f"Registration created: {registration.id}")
                    
                    # Parse team members
                    team_members_str = form.cleaned_data.get('team_members', '').strip()
                    team_members_data = parse_team_members(team_members_str)
                    logger.info(f"Team members data parsed: {len(team_members_data)} members")
                    
                    # Initialize variables
                    team = None
                    team_password = None
                    hashed_password = None
                    added_members = []
                    skipped_members = []
                    
                    # Handle team events
                    if selected_event.is_team_event and team_name_input:
                        logger.info(f"Team event processing: {team_name_input}")
                        
                        # Create team
                        team_password = password
                        hashed_password = make_password(team_password)
                        
                        team = Team.objects.create(
                            name=team_name_input,
                            event=selected_event,
                            created_by=registration,
                            password=hashed_password
                        )
                        logger.info(f"Team created: {team.id} - {team.name}")
                        
                        # Add team leader to TeamMember
                        TeamMember.objects.create(
                            team=team,
                            registration=registration,
                            status='joined'
                        )
                        logger.info(f"Team leader added to TeamMember: {registration.full_name}")
                        
                        # Update registration with team info
                        registration.team = team
                        registration.team_password = hashed_password
                        registration.is_team_lead = True
                        registration.save()
                        logger.info(f"Updated registration with team fields")
                        
                        # Process team members
                        added_members, already_in_team, skipped_members = process_team_members(
                            team, selected_event, team_members_data, registration, 
                            team_name_input, hashed_password
                        )
                        
                        # Update team count
                        total_members = TeamMember.objects.filter(team=team).count()
                        registration.team_members = total_members
                        registration.save()
                        logger.info(f"Updated registration.team_members count: {total_members}")
                        
                        # Store in session
                        request.session['team_password'] = team_password
                        request.session['team_name'] = team_name_input
                        request.session['added_members'] = added_members
                        request.session['skipped_members'] = skipped_members
                    
                    # Create success message
                    success_msg = create_success_message(
                        team_name_input, registration, team_password, 
                        added_members, skipped_members
                    )
                    messages.success(request, success_msg)
                    
                    # Log the user in
                    login(request, user)
                    request.session.save()
                    logger.info(f"User logged in: {user.username}")
                    
                    logger.info("Registration completed successfully, redirecting to success page")
                    return redirect('registration_success')
            
            except IntegrityError as e:
                logger.exception("IntegrityError during registration")
                messages.error(request, 'Registration failed: This register number is already registered. Please check and try again.')
            except ValueError as e:
                logger.exception("ValueError during registration")
                messages.error(request, str(e))
            except Exception as e:
                logger.exception(f"Unexpected error during registration: {str(e)}")
                messages.error(request, f'Registration failed: {str(e)}. Please try again later.')
        else:
            # Display form validation errors
            logger.warning(f"Form validation failed: {form.errors}")
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            messages.error(request, str(error))
                        else:
                            messages.error(request, f'{field.replace("_", " ").title()}: {error}')
    else:
        form = RegistrationForm()
    
    events = Event.objects.all()
    context = {
        'form': form,
        'events': events,
    }
    return render(request, 'core/register.html', context)
def registration_success(request):
    """Display registration success page with latest registration details"""
    # Try to get the most recent registration for context
    registration = None
    team_password = None
    team_name = None
    try:
        registration = Registration.objects.select_related('event').order_by('-registered_at').first()
        # Get team password and name from session
        team_password = request.session.pop('team_password', None)
        team_name = request.session.pop('team_name', None)
    except:
        pass
    
    context = {
        'registration': registration,
        'team_password': team_password,
        'team_name': team_name,
    }
    return render(request, 'core/registration_success.html', context)

def team_details(request, registration_id):
    """Display team details page for team members to join - Using TeamMember table"""
    try:
        registration = Registration.objects.select_related('event', 'team').get(id=registration_id)
    except Registration.DoesNotExist:
        messages.error(request, 'Team not found!')
        return redirect('home')
    
    # Get team members from TeamMember table (not JSON)
    team = registration.team
    if not team:
        messages.error(request, 'Team not found!')
        return redirect('home')
    
    # Get all team members from TeamMember table
    team_members = TeamMember.objects.select_related('registration').filter(team=team).order_by('-status', 'registration__full_name')
    
    context = {
        'registration': registration,
        'team': team,
        'team_name': registration.team_name,
        'event': registration.event,
        'team_members': team_members,
        'total_members': team_members.count(),
        'joined_members': team_members.filter(status='joined').count(),
        'pending_members': team_members.filter(status='pending').count(),
    }
    return render(request, 'core/team_details.html', context)

def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('home')
    
    total_registrations = Registration.objects.count()
    total_participants = Registration.objects.values('register_number').distinct().count()
    total_teams = Team.objects.count()
    recent_registrations = Registration.objects.select_related('event').order_by('-registered_at')[:10]
    
    # Event-wise registration count
    event_stats = []
    events = Event.objects.all()
    for event in events:
        count = Registration.objects.filter(event=event).count()
        event_stats.append({
            'event': event.name,
            'count': count
        })
    
    # Get team statistics
    teams = Team.objects.select_related('event', 'created_by').all().order_by('-created_at')[:10]
    team_stats = []
    for team in teams:
        team_stats.append({
            'id': team.id,
            'name': team.name,
            'event': team.event.name,
            'leader': team.created_by.full_name,
            'members': team.member_count,
            'total': team.total_count,
            'created_at': team.created_at
        })
    
    context = {
        'total_participants': total_participants,
        'total_registrations': total_registrations,
        'total_teams': total_teams,
        'recent_registrations': recent_registrations,
        'event_stats': event_stats,
        'team_stats': team_stats,
    }
    return render(request, 'core/admin_dashboard.html', context)

def view_error_logs(request):
    """View and manage error logs"""
    if not request.user.is_superuser:
        return redirect('home')
    
    # Handle delete all request
    if request.method == 'POST' and request.POST.get('action') == 'delete_all':
        try:
            error_log_path = os.path.join(settings.BASE_DIR, 'logs', 'errors.log')
            if os.path.exists(error_log_path):
                open(error_log_path, 'w').close()  # Clear the file
                messages.success(request, '✅ All error logs have been cleared successfully!')
                logger.info("Admin deleted all error logs")
            else:
                messages.info(request, 'No error log file found.')
        except Exception as e:
            messages.error(request, f'❌ Error clearing logs: {str(e)}')
            logger.error(f"Error deleting error logs: {e}")
    
    # Read error logs
    error_logs = []
    error_log_path = os.path.join(settings.BASE_DIR, 'logs', 'errors.log')
    
    if os.path.exists(error_log_path):
        try:
            with open(error_log_path, 'r') as f:
                lines = f.readlines()
                # Reverse to show newest first
                for line in reversed(lines[-100:]):  # Get last 100 lines
                    if line.strip():
                        error_logs.append(line.strip())
        except Exception as e:
            logger.error(f"Error reading error logs: {e}")
            error_logs = [f"Error reading logs: {str(e)}"]
    
    context = {
        'error_logs': error_logs,
        'total_errors': len(error_logs),
        'error_log_path': error_log_path,
        'log_exists': os.path.exists(error_log_path),
    }
    
    return render(request, 'core/error_logs.html', context)

def contact(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get('user')
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('home')
    else:
        form = LoginForm()
    
    return render(request, 'core/contact.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('contact')

def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            user = User.objects.get(email=email)
            
            # Generate a temporary password
            temp_password = get_random_string(12)
            user.set_password(temp_password)
            user.save()
            
            # Send email with temporary password
            try:
                send_mail(
                    'Password Reset - ARTIFA FEST',
                    f'Your temporary password is: {temp_password}\n\nPlease use this to login and change your password.',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(request, 'A temporary password has been sent to your email address.')
                return redirect('contact')
            except Exception as e:
                messages.error(request, 'Error sending email. Please try again later.')
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'core/forgot_password.html', {'form': form})

@csrf_exempt
def check_registration(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reg_number = data.get('register_number')
            
            # Get registration from Registration database (primary source)
            registration = Registration.objects.filter(register_number=reg_number).select_related('event').first()
            if registration:
                # Optimized: Use select_related for event data and only fetch what we need
                registrations = Registration.objects.filter(
                    register_number=reg_number
                ).select_related('event').values_list('event__name', flat=True)
                
                events_registered = list(registrations)
                
                return JsonResponse({
                    'exists': True,
                    'name': registration.full_name,
                    'email': registration.email,
                    'events': events_registered
                })
            else:
                return JsonResponse({'exists': False})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required(login_url='contact')
def manage_competitions(request):
    if not request.user.is_superuser:
        return redirect('home')
    
    competitions = Event.objects.all().order_by('-created_at')
    
    # Calculate stats for each competition
    competition_list = []
    for comp in competitions:
        reg_count = Registration.objects.filter(event=comp).count()
        competition_list.append({
            'id': comp.id,
            'name': comp.name,
            'type': comp.get_event_type_display(),
            'is_team': comp.is_team_event,
            'team_size': f"{comp.min_team_size}-{comp.max_team_size}" if comp.is_team_event else "N/A",
            'registrations': reg_count,
            'description': comp.description[:100] + '...' if len(comp.description) > 100 else comp.description,
        })
    
    context = {
        'competitions': competition_list,
        'total_competitions': len(competition_list),
    }
    return render(request, 'core/manage_competitions.html', context)

@login_required(login_url='contact')
def add_competition(request):
    if not request.user.is_superuser:
        return redirect('home')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        event_type = request.POST.get('event_type')
        is_team_event = request.POST.get('is_team_event') == 'on'
        min_team_size = int(request.POST.get('min_team_size', 1))
        max_team_size = int(request.POST.get('max_team_size', 1))
        icon_class = request.POST.get('icon_class', 'fas fa-code')
        
        try:
            from django.utils.text import slugify
            slug = slugify(name)
            
            Event.objects.create(
                name=name,
                slug=slug,
                description=description,
                event_type=event_type,
                is_team_event=is_team_event,
                min_team_size=min_team_size,
                max_team_size=max_team_size,
                icon_class=icon_class
            )
            messages.success(request, f'Competition "{name}" created successfully!')
            return redirect('manage_competitions')
        except Exception as e:
            messages.error(request, f'Error creating competition: {str(e)}')
    
    context = {
        'event_types': Event.EVENT_TYPES,
    }
    return render(request, 'core/add_competition.html', context)

@login_required(login_url='contact')
def edit_competition(request, comp_id):
    if not request.user.is_superuser:
        return redirect('home')
    
    comp = Event.objects.get(id=comp_id)
    
    if request.method == 'POST':
        comp.name = request.POST.get('name')
        comp.description = request.POST.get('description')
        comp.event_type = request.POST.get('event_type')
        comp.is_team_event = request.POST.get('is_team_event') == 'on'
        comp.min_team_size = int(request.POST.get('min_team_size', 1))
        comp.max_team_size = int(request.POST.get('max_team_size', 1))
        comp.icon_class = request.POST.get('icon_class', 'fas fa-code')
        
        try:
            comp.save()
            messages.success(request, f'Competition "{comp.name}" updated successfully!')
            return redirect('manage_competitions')
        except Exception as e:
            messages.error(request, f'Error updating competition: {str(e)}')
    
    context = {
        'comp': comp,
        'event_types': Event.EVENT_TYPES,
    }
    return render(request, 'core/edit_competition.html', context)

@login_required(login_url='contact')
def delete_competition(request, comp_id):
    if not request.user.is_superuser:
        return redirect('home')
    
    comp = Event.objects.get(id=comp_id)
    
    if request.method == 'POST':
        comp_name = comp.name
        try:
            comp.delete()
            messages.success(request, f'Competition "{comp_name}" deleted successfully!')
            return redirect('manage_competitions')
        except Exception as e:
            messages.error(request, f'Error deleting competition: {str(e)}')
    
    context = {
        'comp': comp,
        'registration_count': Registration.objects.filter(event=comp).count(),
    }
    return render(request, 'core/delete_competition.html', context)

@login_required(login_url='contact')
def add_admin(request):
    if not request.user.is_superuser:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        
        try:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists!')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists!')
            else:
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name
                )
                messages.success(request, f'Admin user "{username}" created successfully!')
                return redirect('admin_dashboard')
        except Exception as e:
            messages.error(request, f'Error creating admin: {str(e)}')
    
    return render(request, 'core/add_admin.html')

@login_required(login_url='contact')
def manage_schedule(request):
    if not request.user.is_superuser:
        return redirect('home')
    
    schedules = Schedule.objects.all().order_by('date', 'start_time')
    
    # Group by date
    schedule_by_date = {}
    for sched in schedules:
        date_str = sched.date.strftime('%Y-%m-%d')
        if date_str not in schedule_by_date:
            schedule_by_date[date_str] = []
        schedule_by_date[date_str].append({
            'id': sched.id,
            'title': sched.title,
            'start_time': sched.start_time.strftime('%H:%M'),
            'end_time': sched.end_time.strftime('%H:%M'),
            'description': sched.description[:100] + '...' if len(sched.description) > 100 else sched.description,
            'is_break': sched.is_break,
            'event': sched.event.name if sched.event else 'No Event',
        })
    
    context = {
        'schedule_by_date': schedule_by_date,
        'total_schedules': schedules.count(),
    }
    return render(request, 'core/manage_schedule.html', context)

@login_required(login_url='contact')
def add_schedule(request):
    if not request.user.is_superuser:
        return redirect('home')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        is_break = request.POST.get('is_break') == 'on'
        event_id = request.POST.get('event')
        order = int(request.POST.get('order', 0))
        
        try:
            event = None
            if event_id:
                event = Event.objects.get(id=event_id)
            
            Schedule.objects.create(
                title=title,
                description=description,
                date=date,
                start_time=start_time,
                end_time=end_time,
                is_break=is_break,
                event=event,
                order=order
            )
            messages.success(request, f'Schedule "{title}" created successfully!')
            return redirect('manage_schedule')
        except Exception as e:
            messages.error(request, f'Error creating schedule: {str(e)}')
    
    events = Event.objects.all()
    context = {
        'events': events,
    }
    return render(request, 'core/add_schedule.html', context)

@login_required(login_url='contact')
def edit_schedule(request, sched_id):
    if not request.user.is_superuser:
        return redirect('home')
    
    sched = Schedule.objects.get(id=sched_id)
    
    if request.method == 'POST':
        sched.title = request.POST.get('title')
        sched.description = request.POST.get('description')
        sched.date = request.POST.get('date')
        sched.start_time = request.POST.get('start_time')
        sched.end_time = request.POST.get('end_time')
        sched.is_break = request.POST.get('is_break') == 'on'
        sched.order = int(request.POST.get('order', 0))
        
        event_id = request.POST.get('event')
        if event_id:
            sched.event = Event.objects.get(id=event_id)
        else:
            sched.event = None
        
        try:
            sched.save()
            messages.success(request, f'Schedule "{sched.title}" updated successfully!')
            return redirect('manage_schedule')
        except Exception as e:
            messages.error(request, f'Error updating schedule: {str(e)}')
    
    events = Event.objects.all()
    context = {
        'sched': sched,
        'events': events,
    }
    return render(request, 'core/edit_schedule.html', context)

@login_required(login_url='contact')
def delete_schedule(request, sched_id):
    if not request.user.is_superuser:
        return redirect('home')
    
    sched = Schedule.objects.get(id=sched_id)
    
    if request.method == 'POST':
        sched_title = sched.title
        try:
            sched.delete()
            messages.success(request, f'Schedule "{sched_title}" deleted successfully!')
            return redirect('manage_schedule')
        except Exception as e:
            messages.error(request, f'Error deleting schedule: {str(e)}')
    
    context = {
        'sched': sched,
    }
    return render(request, 'core/delete_schedule.html', context)


# ============================================================
# SWEKEER CHATBOT VIEWS
# ============================================================

@csrf_exempt
def chatbot_response(request):
    """API endpoint for SweKeer chatbot with deep learning semantic understanding"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            faq_id = data.get('faq_id', '').strip()  # ✅ Check if user clicked FAQ
            
            if not user_message and not faq_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Message or FAQ ID cannot be empty'
                }, status=400)
            
            # ✅ HANDLE FAQ SELECTION (When user clicks on a common question)
            if faq_id:
                faq_answer = chatbot.get_faq_answer(faq_id)
                if faq_answer.get('found'):
                    return JsonResponse({
                        'success': True,
                        'message': faq_answer['answer'],
                        'type': 'faq',
                        'chatbot_name': 'SWEKEER-FAQ',
                        'confidence': 1.0,
                        'intent': 'faq',
                        'found_in_dataset': True,
                        'is_faq': True,
                        'model_used': 'faq'
                    })
            
            # Try enhanced deep learning approach
            try:
                from core.chatbot_enhanced import get_intelligent_response
                response_data = get_intelligent_response(user_message)
                
                if response_data.get('model') != 'none':
                    return JsonResponse({
                        'success': True,
                        'message': response_data.get('response'),
                        'type': response_data.get('model'),
                        'chatbot_name': 'SWEKEER-DL',
                        'confidence': response_data.get('confidence'),
                        'intent': response_data.get('intent'),
                        'found_in_dataset': True,
                        'model_used': response_data.get('model')
                    })
            except Exception as e:
                logger.warning(f"Deep learning approach failed: {e}")
            
            # ✅ CHECK FAQ MATCH FIRST (Before database search)
            faq_match = chatbot.search_faq_by_query(user_message)
            if faq_match:
                return JsonResponse({
                    'success': True,
                    'message': faq_match['answer'],
                    'type': 'faq',
                    'chatbot_name': 'SWEKEER-FAQ',
                    'confidence': faq_match['confidence'],
                    'intent': 'faq',
                    'found_in_dataset': True,
                    'is_faq': True,
                    'model_used': 'faq'
                })
            
            # FALLBACK: Traditional semantic search with optimized threshold
            answer, confidence, training_pair = ChatbotTraining.find_answer(user_message, confidence_threshold=0.2)
            
            if answer:
                # Found in dataset with sufficient confidence
                return JsonResponse({
                    'success': True,
                    'message': answer,
                    'type': 'training_data',
                    'chatbot_name': 'SWEKEER',
                    'confidence': confidence,
                    'intent': training_pair.intent if training_pair else None,
                    'found_in_dataset': True,
                    'model_used': 'traditional'
                })
            
            # SECONDARY OPTION: If not found in dataset, show FAQ suggestions + other suggestions
            # Get FAQ questions for suggestions
            faq_questions = chatbot.get_faq_questions()
            
            # Get other suggestions from database
            suggestions = ChatbotTraining.get_suggestions(limit=3)
            other_suggestions = [
                {
                    'question': s.question,
                    'id': s.id,
                    'intent': s.intent,
                    'type': 'knowledge'
                }
                for s in suggestions
            ]
            
            # Combine FAQ and other suggestions
            all_suggestions = [{'question': faq['question'], 'id': faq['id'], 'type': 'faq'} for faq in faq_questions] + other_suggestions
            
            # Prepare fallback message
            fallback_message = f"""I couldn't find an exact answer to that question. However, here are some common topics I can help with:

**Common Questions (Click any to get answer):**
{chr(10).join([f"• {s['question']}" for s in faq_questions[:5]])}

Would you like to ask one of these questions instead?"""
            
            return JsonResponse({
                'success': True,
                'message': fallback_message,
                'type': 'suggestions',
                'chatbot_name': 'SWEKEER',
                'suggestions': all_suggestions,
                'found_in_dataset': False,
                'note': 'No exact match found. Here are available topics.',
                'model_used': 'none'
            })
        
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON format'
            }, status=400)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Chatbot Error: {str(e)}\n{error_detail}")
            logger.error(f"Chatbot Error: {str(e)}\n{error_detail}")
            return JsonResponse({
                'success': False,
                'error': f"Error: {str(e)}"
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Only POST requests are allowed'
    }, status=405)

def view_registrations(request):
    """View team leads with their team names and members"""
    if not request.user.is_superuser:
        return redirect('home')
    
    # Check if viewing team members
    view_mode = request.GET.get('view', 'teams')  # 'teams' or 'members'
    team_id = request.GET.get('team_id')
    
    # If viewing team members
    if view_mode == 'members' and team_id:
        try:
            team = Team.objects.select_related('created_by', 'event').get(id=team_id)
            team_members = TeamMember.objects.select_related('registration').filter(team=team).order_by('-status', 'registration__full_name')
            
            context = {
                'view_mode': 'members',
                'team': team,
                'team_members': team_members,
                'page_title': f'Team Members - {team.name}',
            }
            return render(request, 'core/view_team_members.html', context)
        except Team.DoesNotExist:
            messages.error(request, 'Team not found.')
            return redirect('view_registrations')
    
    # Default: Show all team leads
    # Get all registrations that are team leads
    team_leads = Registration.objects.filter(
        is_team_lead=True
    ).select_related('team', 'event').order_by('team_name', 'full_name')
    
    # Add team members count for each team
    team_data = []
    for lead in team_leads:
        if lead.team:
            team_members = TeamMember.objects.filter(team=lead.team)
            team_info = {
                'lead': lead,
                'team': lead.team,
                'total_members': team_members.count(),
                'joined_members': team_members.filter(status='joined').count(),
                'pending_members': team_members.filter(status='pending').count(),
            }
            team_data.append(team_info)
    
    # Get all registrations for fallback view
    registrations = Registration.objects.select_related('event').all()
    
    # Note: team_members is now an IntegerField (count), not JSON
    # No need to parse it anymore
    
    # Get query parameters for filtering
    sort_by = request.GET.get('sort_by', 'name')  # name, dept, year, event, team
    
    # Sort registrations
    if sort_by == 'dept':
        registrations = registrations.order_by('department', 'full_name')
    elif sort_by == 'year':
        registrations = registrations.order_by('year', 'full_name')
    elif sort_by == 'event':
        registrations = registrations.order_by('event__name', 'full_name')
    elif sort_by == 'team':
        registrations = registrations.order_by('team_name', 'full_name')
    else:  # Default: sort by name
        registrations = registrations.order_by('full_name')
    
    # Get statistics (use Registration as primary source)
    total_registrations = Registration.objects.count()
    total_participants = Registration.objects.values('register_number').distinct().count()
    total_events = Event.objects.count()
    
    # Count team registrations
    team_registrations = Registration.objects.filter(team_name__isnull=False, team_name__gt='').count()
    individual_registrations = total_registrations - team_registrations
    
    # Group registrations by different criteria
    registrations_by_name = {}
    registrations_by_dept = {}
    registrations_by_year = {}
    registrations_by_event = {}
    registrations_by_team = {}
    
    try:
        for reg in Registration.objects.select_related('event').all():
            # Note: team_members is now an IntegerField (count), not JSON
            # No need to parse it anymore
            
            # Group by name
            name = reg.full_name
            if name not in registrations_by_name:
                registrations_by_name[name] = []
            registrations_by_name[name].append(reg)
            
            # Group by department
            try:
                dept = reg.get_department_display()
            except:
                dept = reg.department
            if dept not in registrations_by_dept:
                registrations_by_dept[dept] = []
            registrations_by_dept[dept].append(reg)
            
            # Group by year
            try:
                year = reg.get_year_display()
            except:
                year = reg.year
            if year not in registrations_by_year:
                registrations_by_year[year] = []
            registrations_by_year[year].append(reg)
            
            # Group by event
            event_name = reg.event.name
            if event_name not in registrations_by_event:
                registrations_by_event[event_name] = []
            registrations_by_event[event_name].append(reg)
            
            # Group by team
            team_name = reg.team_name if reg.team_name else 'Solo'
            if team_name not in registrations_by_team:
                registrations_by_team[team_name] = []
            registrations_by_team[team_name].append(reg)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Error grouping registrations")
        # Continue with partial data if grouping fails
        pass
    
    # Sort the grouped dictionaries with None handling
    registrations_by_name = dict(sorted(registrations_by_name.items(), key=lambda x: (x[0] is None, x[0])))
    registrations_by_dept = dict(sorted(registrations_by_dept.items(), key=lambda x: (x[0] is None, x[0])))
    registrations_by_year = dict(sorted(registrations_by_year.items(), key=lambda x: (x[0] is None, x[0])))
    registrations_by_event = dict(sorted(registrations_by_event.items(), key=lambda x: (x[0] is None, x[0])))
    registrations_by_team = dict(sorted(registrations_by_team.items(), key=lambda x: (x[0] is None, x[0])))
    
    context = {
        'view_mode': 'teams',
        'team_data': team_data,
        'registrations': registrations,
        'registrations_by_name': registrations_by_name,
        'registrations_by_dept': registrations_by_dept,
        'registrations_by_year': registrations_by_year,
        'registrations_by_event': registrations_by_event,
        'registrations_by_team': registrations_by_team,
        'total_registrations': total_registrations,
        'total_participants': total_participants,
        'total_events': total_events,
        'team_registrations': team_registrations,
        'individual_registrations': individual_registrations,
        'sort_by': sort_by,
        'page_title': 'Team Leads & Members',
    }
    
    return render(request, 'core/view_registrations.html', context)

def export_registrations(request):
    """Export registrations as CSV"""
    if not request.user.is_superuser:
        return redirect('home')
    
    import csv
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="registrations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Participant Name', 'Register Number', 'Year', 'Department', 'Phone', 'Email', 'Event Name', 'Event Type', 'Event Time', 'Team Name', 'Registered Date'])
    
    registrations = Registration.objects.select_related('event').order_by('full_name', 'event__name')
    
    for reg in registrations:
        event_time = ''
        if reg.event.start_time and reg.event.end_time:
            event_time = f"{reg.event.start_time.strftime('%H:%M')} - {reg.event.end_time.strftime('%H:%M')}"
        
        writer.writerow([
            reg.full_name,
            reg.register_number,
            reg.get_year_display(),
            reg.get_department_display(),
            reg.phone_number,
            reg.email,
            reg.event.name,
            reg.event.get_event_type_display(),
            event_time,
            reg.team_name or '',
            reg.registered_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    
    return response

@login_required(login_url='contact')
def manage_event(request, event_id=None):
    """Create or edit an event with time information"""
    if not request.user.is_superuser:
        return redirect('home')
    
    event = None
    if event_id:
        event = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            try:
                form.save()
                event_action = 'updated' if event else 'created'
                messages.success(request, f'Event "{form.cleaned_data["name"]}" {event_action} successfully!')
                return redirect('manage_events')
            except Exception as e:
                messages.error(request, f'Error saving event: {str(e)}')
    else:
        form = EventForm(instance=event)
    
    context = {
        'form': form,
        'event': event,
        'is_edit': event is not None,
    }
    return render(request, 'core/manage_event.html', context)


@login_required(login_url='contact')
def manage_coordinators(request, event_id=None):
    """Manage coordinators for an event"""
    if not request.user.is_superuser:
        return redirect('home')
    
    event = None
    if event_id:
        event = get_object_or_404(Event, id=event_id)
    
    coordinators = Coordinator.objects.all()
    if event:
        coordinators = coordinators.filter(event=event)
    
    context = {
        'event': event,
        'coordinators': coordinators,
    }
    return render(request, 'core/manage_coordinators.html', context)


@login_required(login_url='contact')
def add_coordinator(request, event_id=None):
    """Add a new coordinator"""
    if not request.user.is_superuser:
        return redirect('home')
    
    event = None
    if event_id:
        event = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        form = CoordinatorForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'Coordinator added successfully!')
                if event:
                    return redirect('manage_coordinators', event_id=event.id)
                return redirect('manage_coordinators')
            except Exception as e:
                messages.error(request, f'Error adding coordinator: {str(e)}')
    else:
        form = CoordinatorForm()
        if event:
            form.fields['event'].initial = event
    
    context = {
        'form': form,
        'event': event,
        'is_add': True,
    }
    return render(request, 'core/coordinator_form.html', context)


@login_required(login_url='contact')
def edit_coordinator(request, coordinator_id):
    """Edit an existing coordinator"""
    if not request.user.is_superuser:
        return redirect('home')
    
    coordinator = get_object_or_404(Coordinator, id=coordinator_id)
    
    if request.method == 'POST':
        form = CoordinatorForm(request.POST, instance=coordinator)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Coordinator updated successfully!')
                return redirect('manage_coordinators', event_id=coordinator.event.id)
            except Exception as e:
                messages.error(request, f'Error updating coordinator: {str(e)}')
    else:
        form = CoordinatorForm(instance=coordinator)
    
    context = {
        'form': form,
        'coordinator': coordinator,
        'is_edit': True,
    }
    return render(request, 'core/coordinator_form.html', context)


@login_required(login_url='contact')
def delete_coordinator(request, coordinator_id):
    """Delete a coordinator"""
    if not request.user.is_superuser:
        return redirect('home')
    
    coordinator = get_object_or_404(Coordinator, id=coordinator_id)
    event = coordinator.event
    
    if request.method == 'POST':
        try:
            coordinator.delete()
            messages.success(request, 'Coordinator deleted successfully!')
            return redirect('manage_coordinators', event_id=event.id)
        except Exception as e:
            messages.error(request, f'Error deleting coordinator: {str(e)}')
    
    context = {
        'coordinator': coordinator,
    }
    return render(request, 'core/confirm_delete_coordinator.html', context)

# Error Handlers
def test_500_error(request):
    """Test view to trigger 500 error"""
    raise Exception("This is a test 500 error")

def test_403_error(request):
    """Test view to trigger 403 error"""
    from django.core.exceptions import PermissionDenied
    raise PermissionDenied("This is a test 403 error")

def test_400_error(request):
    """Test view to trigger 400 error"""
    from django.http import HttpResponseBadRequest
    return HttpResponseBadRequest("This is a test 400 error")

def error_404(request, exception=None):
    """Handle 404 Not Found errors"""
    from .models import ErrorLog
    import logging
    
    logger = logging.getLogger(__name__)
    logger.warning(f"404 Not Found: {request.path} from {request.META.get('REMOTE_ADDR')}")
    
    return render(request, '404.html', status=404)

def error_500(request):
    """Handle 500 Internal Server Error"""
    from .models import ErrorLog
    import logging
    import uuid
    
    logger = logging.getLogger(__name__)
    error_id = str(uuid.uuid4())
    logger.error(f"500 Server Error: {error_id} from {request.path}")
    
    context = {
        'error_id': error_id,
    }
    return render(request, '500.html', context, status=500)

def error_403(request, exception=None):
    """Handle 403 Forbidden errors"""
    return render(request, 'core/error_403.html', status=403)

def error_400(request, exception=None):
    """Handle 400 Bad Request errors"""
    return render(request, 'core/error_400.html', status=400)


@login_required(login_url='contact')
def send_alert(request):
    """Send alert messages to registered participants via email with optional image attachment"""
    if request.method == 'POST':
        form = SendAlertForm(request.POST, request.FILES)
        if form.is_valid():
            recipient_type = form.cleaned_data['recipient_type']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            image = form.cleaned_data.get('image')
            
            try:
                # Get recipients - ONLY registered participants (from Registration dataset)
                if recipient_type == 'all':
                    # Get registrations with unique email addresses
                    registrations = Registration.objects.filter(
                        email__isnull=False
                    ).exclude(email='').distinct()
                    alert_type = "All Registered Participants"
                else:
                    event = form.cleaned_data['event']
                    registrations = Registration.objects.filter(
                        event=event
                    ).filter(
                        email__isnull=False
                    ).exclude(email='').distinct()
                    alert_type = f"Event: {event.name}"
                
                # Collect email addresses from Registration dataset
                emails = [r.email for r in registrations if r.email]
                
                if not emails:
                    messages.error(request, 'No valid email addresses found for selected recipients.')
                    return redirect('send_alert')
                
                # Send emails with optional attachment
                from django.core.mail import EmailMessage
                import mimetypes
                from io import BytesIO
                
                # Read image once if provided (to avoid file pointer issues with multiple emails)
                image_content = None
                image_name = None
                image_type = None
                
                if image:
                    try:
                        # Read the image file
                        image.seek(0)
                        image_content = image.read()
                        image_name = image.name
                        
                        # Determine correct MIME type
                        mime_type, _ = mimetypes.guess_type(image_name)
                        if not mime_type:
                            # Fallback to image/jpeg for common formats
                            if image_name.lower().endswith('.png'):
                                mime_type = 'image/png'
                            elif image_name.lower().endswith('.gif'):
                                mime_type = 'image/gif'
                            elif image_name.lower().endswith('.webp'):
                                mime_type = 'image/webp'
                            else:
                                mime_type = 'image/jpeg'
                        
                        image_type = mime_type
                        print(f"✅ Image prepared: {image_name} ({len(image_content)} bytes, type: {image_type})")
                    except Exception as img_error:
                        print(f"❌ Error reading image: {str(img_error)}")
                        image_content = None
                
                for email_to in emails:
                    email = EmailMessage(
                        subject=subject,
                        body=message,
                        from_email=settings.EMAIL_HOST_USER,
                        to=[email_to],
                    )
                    
                    # Attach image if provided
                    if image_content and image_name and image_type:
                        try:
                            # Attach the image as an attachment
                            email.attach(image_name, image_content, image_type)
                        except Exception as attach_error:
                            pass  # Continue even if attachment fails
                    
                    email.send(fail_silently=False)
                
                attachment_text = " with image" if image else ""
                messages.success(
                    request, 
                    f'✅ Alert sent successfully{attachment_text} to {len(emails)} participants ({alert_type})!'
                )
                return redirect('send_alert')
                
            except Exception as e:
                import traceback
                messages.error(request, f'Error sending alert: {str(e)}. Check logs for details.')
                # Log the full error
                import logging
                logger = logging.getLogger('core')
                logger.error(f"Alert send error: {traceback.format_exc()}")
    else:
        form = SendAlertForm()
    
    # Get statistics - from Registration dataset (primary source)
    total_registered = Registration.objects.values('register_number').distinct().count()
    total_participants = total_registered
    events = Event.objects.all()
    
    context = {
        'form': form,
        'total_participants': total_participants,
        'total_registered': total_registered,
        'events': events,
    }
    return render(request, 'core/send_alert.html', context)

def send_test_email(request):
    """Send a test email with optional image"""
    if request.method == 'POST':
        try:
            test_email = request.POST.get('test_email')
            subject = request.POST.get('subject')
            message_text = request.POST.get('message')
            image = request.FILES.get('image')
            
            if not test_email or not subject or not message_text:
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required fields'
                })
            
            from django.core.mail import EmailMessage
            
            email = EmailMessage(
                subject=subject,
                body=message_text,
                from_email=settings.EMAIL_HOST_USER,
                to=[test_email],
            )
            
            # Attach image if provided
            if image:
                image.seek(0)
                email.attach(image.name, image.read(), image.content_type)
                attachment_text = " with image"
            else:
                attachment_text = ""
            
            email.send(fail_silently=False)
            
            return JsonResponse({
                'success': True,
                'message': f'Test email sent successfully{attachment_text} to {test_email}!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request'})


# ============================================================
# EDIT AND DELETE PARTICIPANTS AND REGISTRATIONS
# ============================================================

@login_required(login_url='student_login')
def edit_registration(request, registration_id):
    """Edit a registration with full member details"""
    registration = get_object_or_404(Registration, id=registration_id)
    
    # Check if user is admin (only admins can edit registrations)
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to edit this registration.')
        return redirect('home')
    
    if request.method == 'POST':
        # Update participant details
        registration.full_name = request.POST.get('full_name', '').strip()
        registration.email = request.POST.get('email', '').strip()
        registration.phone_number = request.POST.get('phone_number', '').strip()
        registration.register_number = request.POST.get('register_number', '').strip()
        registration.year = request.POST.get('year', '')
        registration.department = request.POST.get('department', '')
        
        # Update event and team details
        event_id = request.POST.get('event')
        if event_id:
            event = get_object_or_404(Event, id=event_id)
            registration.event = event
        
        registration.team_name = request.POST.get('team_name', '').strip()
        team_members_str = request.POST.get('team_members', '0').strip()
        try:
            registration.team_members = int(team_members_str)
        except ValueError:
            registration.team_members = 0
        
        registration.is_team_lead = request.POST.get('is_team_lead') == 'on'
        registration.is_verified = request.POST.get('is_verified') == 'on'
        
        registration.save()
        messages.success(request, f'Registration for {registration.full_name} updated successfully!')
        return redirect('view_registrations')
    
    context = {
        'registration': registration,
        'events': Event.objects.all(),
        'year_choices': Registration.YEAR_CHOICES,
        'department_choices': Registration.DEPARTMENT_CHOICES,
    }
    return render(request, 'core/edit_registration.html', context)


def delete_registration(request, registration_id):
    """Delete a registration"""
    if not request.user.is_superuser:
        return redirect('home')
    
    registration = get_object_or_404(Registration, id=registration_id)
    
    if request.method == 'POST':
        registration_name = registration.full_name
        event_name = registration.event.name
        registration.delete()
        messages.success(request, f'Registration deleted: {registration_name} from {event_name}!')
        return redirect('view_registrations')
    
    context = {'registration': registration}
    return render(request, 'core/confirm_delete_registration.html', context)



# ========================= TEAM MANAGEMENT =========================

from .models import Team, TeamMember

def can_manage_team(request, team):
    """Check if user can manage this team (must be team leader or admin)"""
    if not request.user.is_authenticated:
        return False
    
    # Admin/Superuser can always manage teams
    if request.user.is_superuser or request.user.is_staff:
        return True
    
    # Regular users must be team leader
    try:
        participant = request.user.participant_profile
        return team.created_by == participant
    except Participant.DoesNotExist:
        return False


@login_required(login_url='student_login')
def view_team(request, team_id):
    """View team details and members using Registration database"""
    team = get_object_or_404(Team, id=team_id)
    
    # Admin can always view
    is_admin = request.user.is_superuser or request.user.is_staff
    
    # Get team members from TeamMember table
    members = team.members.select_related('registration', 'registration__event').all()
    
    # Get team registrations from Registration database
    registrations = Registration.objects.filter(team=team).select_related('event')
    
    # Check authorization for non-admin users
    is_team_leader = False
    is_team_member = False
    
    if not is_admin and request.user.is_authenticated:
        # Check if user's registration is in this team
        user_registrations = Registration.objects.filter(user=request.user)
        user_in_team = user_registrations.filter(team=team).exists()
        is_team_member = user_in_team
        is_team_leader = team.created_by and team.created_by.user == request.user
        
        if not is_team_leader and not is_team_member:
            messages.error(request, 'You do not have permission to view this team.')
            return redirect('home')
    
    context = {
        'team': team,
        'members': members,
        'registrations': registrations,
        'is_team_leader': is_team_leader,
        'is_team_member': is_team_member,
        'is_admin': is_admin,
        'event_max_size': team.event.max_team_size,
        'current_member_count': team.member_count,
    }
    return render(request, 'core/view_team.html', context)


@login_required(login_url='student_login')
def add_team_members_after_registration(request, registration_id):
    """Add team members after registration for team events - Team Lead Only"""
    try:
        registration = Registration.objects.select_related('participant', 'event').get(
            id=registration_id,
            participant__user=request.user
        )
    except Registration.DoesNotExist:
        messages.error(request, 'Registration not found or you do not have permission.')
        return redirect('student_dashboard')
    
    # Check if event is a team event
    if not registration.event.is_team_event:
        messages.error(request, 'This event does not require team members.')
        return redirect('student_dashboard')
    
    # Check if team already exists for this registration
    team = Team.objects.filter(registration=registration).first()
    if team:
        messages.info(request, 'Team already created for this registration.')
        return redirect('view_team', team_id=team.id)
    
    # Create team with team lead as registration participant
    if request.method == 'GET' and not team:
        team = Team.objects.create(
            registration=registration,
            name=registration.team_name or f'{registration.participant.full_name}\'s Team',
            created_by=registration.participant,
            event=registration.event
        )
        
        # Add team lead as member
        TeamMember.objects.create(
            team=team,
            participant=registration.participant,
            status='joined'
        )
        
        messages.success(request, f'Team "{team.name}" created successfully!')
    
    if request.method == 'POST':
        team_member_count = request.POST.get('member_count', 0)
        
        try:
            team_member_count = int(team_member_count)
        except ValueError:
            messages.error(request, 'Invalid member count.')
            return redirect('add_team_members_after_registration', registration_id=registration_id)
        
        # Validate member count (including team lead)
        # team_member_count is the number of additional members (0+)
        # total team size = team_member_count + 1 (for team lead)
        total_team_size = team_member_count + 1
        
        if total_team_size < registration.event.min_team_size:
            messages.error(request, f'Minimum {registration.event.min_team_size} members required.')
            return redirect('add_team_members_after_registration', registration_id=registration_id)
        
        if total_team_size > registration.event.max_team_size:
            messages.error(request, f'Maximum {registration.event.max_team_size} members allowed.')
            return redirect('add_team_members_after_registration', registration_id=registration_id)
        
        # Get team (should exist now)
        team = Team.objects.filter(registration=registration).first()
        if not team:
            messages.error(request, 'Team creation failed.')
            return redirect('student_dashboard')
        
        # If form was submitted with member invitations
        if 'add_members' in request.POST:
            # Parse members data
            members_data = {}
            for i in range(0, team_member_count):
                register_number = request.POST.get(f'member_register_{i}', '').strip()
                if register_number:
                    members_data[register_number] = i
            
            # Add members to team
            added_count = 0
            for register_number in members_data.keys():
                try:
                    # Get participant from Registration dataset (primary source)
                    member_reg_obj = Registration.objects.filter(register_number=register_number).select_related('team').first()
                    if not member_reg_obj:
                        raise Participant.DoesNotExist
                    member_participant = member_reg_obj.participant
                    
                    # Check if already in team
                    if TeamMember.objects.filter(team=team, participant=member_participant).exists():
                        messages.warning(request, f'{member_participant.full_name} is already in the team.')
                        continue
                    
                    # Add member
                    TeamMember.objects.create(
                        team=team,
                        participant=member_participant,
                        status='pending'
                    )
                    added_count += 1
                
                except Participant.DoesNotExist:
                    messages.warning(request, f'Register number {register_number} not found.')
            
            if added_count > 0:
                messages.success(request, f'{added_count} team member(s) invited successfully!')
                return redirect('view_team', team_id=team.id)
            else:
                messages.error(request, 'No members were added. Please check register numbers.')
    
    # Get current team if exists
    team = Team.objects.filter(registration=registration).first()
    current_members = TeamMember.objects.filter(team=team).count() if team else 0
    
    context = {
        'registration': registration,
        'team': team,
        'event': registration.event,
        'team_name': registration.team_name or f'{registration.participant.full_name}\'s Team',
        'members_needed': registration.event.max_team_size,
        'current_members': current_members,
        'min_members': registration.event.min_team_size,
        'max_members': registration.event.max_team_size,
    }
    return render(request, 'core/add_team_members_registration.html', context)


def create_team(request, event_id):
    """Create a new team for a team event"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is authenticated
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to create a team.')
        return redirect('student_login')
    
    # Get or create registration for the user
    registration = None
    if request.user.is_superuser or request.user.is_staff:
        # Admin can proceed
        pass
    else:
        # Try to get registration for regular users
        try:
            registration = Registration.objects.get(user=request.user, event=event)
        except Registration.DoesNotExist:
            messages.error(request, 'Please register for this event first.')
            return redirect('register')
    
    # Verify it's a team event
    if not event.is_team_event:
        messages.error(request, 'This event does not support teams.')
        return redirect('home')
    
    if request.method == 'POST':
        team_name = request.POST.get('team_name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not team_name:
            messages.error(request, 'Team name is required.')
            return render(request, 'core/create_team.html', {'event': event})
        
        # Check if team name already exists for this event
        if Team.objects.filter(name=team_name, event=event).exists():
            messages.error(request, f'A team with name "{team_name}" already exists for {event.name}. Please use a different name.')
            return render(request, 'core/create_team.html', {'event': event})
        
        try:
            with transaction.atomic():
                # ✅ VALIDATE EVENT REGISTRATION LIMITS before creating team
                if registration:
                    is_valid, error_msg = validate_event_registration_limit(registration.register_number, event)
                    if not is_valid:
                        logger.warning(f"Event registration limit validation failed: {error_msg}")
                        messages.error(request, error_msg)
                        return render(request, 'core/create_team.html', {'event': event})
                
                # Generate team password (6 characters)
                team_password = get_random_string(6)
                hashed_password = make_password(team_password)
                
                # Create team with team leader's Registration ✅
                team = Team.objects.create(
                    name=team_name,
                    event=event,
                    created_by=registration,  # ✅ FK to Registration (team leader)
                    description=description,
                    password=hashed_password
                )
                logger.info(f"Team created: {team.id} with created_by=Registration#{registration.id}")
                
                # Add creator as first member with 'joined' status ✅
                TeamMember.objects.create(
                    team=team,
                    registration=registration,  # ✅ Link Registration to Team
                    status='joined'
                )
                logger.info(f"Team leader added to TeamMember with status=joined")
                
                # Update Registration with team reference ✅
                registration.team = team
                registration.team_name = team_name
                registration.team_password = hashed_password
                registration.is_team_lead = True
                registration.save()
                logger.info(f"Updated Registration#{registration.id} with team_id={team.id} and team_password")
                
                # Store in session for team login
                request.session['team_id'] = team.id
                request.session['team_name'] = team_name
                request.session['team_logged_in'] = True
                request.session.save()
                
                messages.success(request, f'✅ Team "{team_name}" created! Team Password: {team_password}')
                # Redirect to add members page
                return redirect('team_add_members', team_id=team.id)
        
        except IntegrityError as e:
            logger.error(f"IntegrityError creating team: {e}")
            messages.error(request, f'Team creation failed: Team name must be unique for this event.')
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error creating team: {str(e)}')
    
    context = {'event': event}
    return render(request, 'core/create_team.html', context)


# ============ TEAM LOGIN DECORATOR ============
def team_login_required(view_func):
    """Decorator to check if team is logged in via session (Admin/Superuser bypass)"""
    from functools import wraps
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Allow admin/superuser to bypass team login requirement
        if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
            # Admin access granted - mark in request
            request.is_admin_access = True
            return view_func(request, *args, **kwargs)
        
        # Regular team login check
        if 'team_id' not in request.session or not request.session.get('team_logged_in'):
            messages.error(request, 'Please log in as a team first.')
            return redirect('team_login')
        return view_func(request, *args, **kwargs)
    return wrapped_view


@team_login_required
def team_add_members(request, team_id):
    """Add/Edit/Delete team members using Registration database"""
    team = get_object_or_404(Team, id=team_id)
    
    # Verify team matches session
    if team.id != request.session.get('team_id'):
        messages.error(request, 'Team access denied.')
        return redirect('team_login')
    
    # Check authorization - only team leader or admin
    is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff)
    is_leader = False
    
    if not is_admin:
        # Check if user created this team (if logged in)
        if request.user.is_authenticated:
            is_leader = team.created_by and team.created_by.user == request.user
        
        # Allow access to team if logged in via team_login
        if not is_leader and request.user.is_authenticated:
            messages.error(request, 'You do not have permission to manage this team.')
            return redirect('team_dashboard')
    
    # Handle member operations
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_member':
            # Get member details from form
            full_name = request.POST.get('full_name', '').strip()
            register_number = request.POST.get('register_number', '').strip().upper()
            email = request.POST.get('email', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            department = request.POST.get('department', '').strip()
            year = request.POST.get('year', '').strip()
            
            # Validate required fields
            if not all([full_name, register_number, email, phone_number, department, year]):
                messages.error(request, 'All fields are required.')
            elif team.total_count >= team.event.max_team_size:
                remaining_slots = team.event.max_team_size - team.total_count
                messages.error(request, f'❌ Team is full! Maximum {team.event.max_team_size} members allowed. Current: {team.total_count}/{team.event.max_team_size}')
            else:
                try:
                    # ✅ VALIDATE EVENT REGISTRATION LIMITS for the member
                    is_valid, error_msg = validate_event_registration_limit(register_number, team.event)
                    if not is_valid:
                        logger.warning(f"Event registration limit validation failed for member {register_number}: {error_msg}")
                        messages.error(request, error_msg)
                    else:
                        # Check if member already exists in team by register number
                        existing_member = Registration.objects.filter(
                            register_number=register_number,
                            event=team.event
                        ).first()
                        
                        if existing_member and TeamMember.objects.filter(team=team, registration=existing_member).exists():
                            messages.warning(request, f'{existing_member.full_name} is already in this team.')
                        else:
                            # Double-check team capacity before adding
                            if team.total_count >= team.event.max_team_size:
                                messages.error(request, f'❌ Team capacity exceeded! Maximum: {team.event.max_team_size}, Current: {team.total_count}')
                            else:
                                # Create or get Registration record
                                registration, created = Registration.objects.get_or_create(
                                    register_number=register_number,
                                    event=team.event,
                                    defaults={
                                        'full_name': full_name,
                                        'email': email,
                                        'phone_number': phone_number,
                                        'department': department,
                                        'year': year,
                                        'team': team,  # ✅ SET TEAM DATA
                                        'team_name': team.name,  # ✅ STORE TEAM NAME
                                        'team_password': team.password,  # ✅ STORE TEAM PASSWORD
                                    }
                                )
                                
                                # Update fields if exists and ensure team data is always set
                                if not created:
                                    registration.full_name = full_name
                                    registration.email = email
                                    registration.phone_number = phone_number
                                    registration.department = department
                                    registration.year = year
                                    registration.team = team  # ✅ ENSURE TEAM DATA SET
                                    registration.team_name = team.name  # ✅ ENSURE TEAM NAME SET
                                    registration.team_password = team.password  # ✅ ENSURE TEAM PASSWORD SET
                                    registration.save()
                                
                                # Create TeamMember
                                team_member, member_created = TeamMember.objects.get_or_create(
                                    team=team,
                                    registration=registration,
                                    defaults={'status': 'pending', 'added_at': timezone.now()}
                                )
                                
                                if member_created:
                                    # Calculate remaining capacity
                                    remaining_slots = team.event.max_team_size - team.total_count
                                    messages.success(request, f'✅ {full_name} added as pending! ({team.total_count}/{team.event.max_team_size}) - {remaining_slots} slot{"s" if remaining_slots != 1 else ""} remaining')
                                else:
                                    messages.info(request, f'{full_name} is already in the team.')
                
                except Exception as e:
                    messages.error(request, f'Error adding member: {str(e)}')
        
        elif action == 'remove_member':
            member_id = request.POST.get('member_id')
            try:
                team_member = TeamMember.objects.get(id=member_id, team=team)
                if team_member.registration == team.created_by:
                    messages.error(request, 'Cannot remove team leader.')
                else:
                    member_name = team_member.registration.full_name
                    team_member.delete()
                    messages.success(request, f'{member_name} removed from team. ({team.total_count}/{team.event.max_team_size})')
            except TeamMember.DoesNotExist:
                messages.error(request, 'Member not found.')
        
        elif action == 'finalize':
            # Check minimum team size
            if team.member_count < team.event.min_team_size:
                messages.error(request, f'❌ Team must have at least {team.event.min_team_size} members. Current: {team.member_count} (Pending: {team.pending_count})')
            elif team.total_count > team.event.max_team_size:
                messages.error(request, f'❌ Team exceeds maximum size! Max: {team.event.max_team_size}, Current: {team.total_count}')
            else:
                messages.success(request, f'✅ Team "{team.name}" finalized successfully! ({team.member_count}/{team.event.max_team_size})')
                return redirect('registration_success')
    
    # Get team members from TeamMember
    members = team.members.select_related('registration', 'registration__event').all()
    
    # Calculate progress percentage
    progress_percent = 0
    if team.event.max_team_size > 0:
        progress_percent = int((team.member_count / team.event.max_team_size) * 100)
    
    context = {
        'team': team,
        'members': members,
        'event': team.event,
        'event_max_size': team.event.max_team_size,
        'event_min_size': team.event.min_team_size,
        'current_member_count': team.member_count,
        'progress_percent': progress_percent,
        'is_leader': is_leader,
        'is_admin': is_admin,
    }
    return render(request, 'core/team_add_members.html', context)


@team_login_required
def add_team_member(request, team_id):
    """Add a team member using Registration database"""
    team = get_object_or_404(Team, id=team_id)
    
    # Verify team matches session
    if team.id != request.session.get('team_id'):
        messages.error(request, 'Team access denied.')
        return redirect('team_login')
    
    # Check authorization
    is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff)
    is_leader = False
    
    if not is_admin:
        # Check if user created this team (if logged in)
        if request.user.is_authenticated:
            is_leader = team.created_by and team.created_by.user == request.user
        
        # Allow access to team if logged in via team_login
        if not is_leader and request.user.is_authenticated:
            messages.error(request, 'You do not have permission to manage this team.')
            return redirect('team_dashboard')
    
    # Check if team is full
    if team.total_count >= team.event.max_team_size:
        messages.error(request, f'Team is full (maximum {team.event.max_team_size} members).')
        return redirect('view_team', team_id=team_id)
    
    if request.method == 'POST':
        register_number = request.POST.get('register_number', '').strip().upper()
        
        if not register_number:
            messages.error(request, 'Register number is required.')
            return render(request, 'core/add_team_member.html', {'team': team})
        
        try:
            # ✅ VALIDATE EVENT REGISTRATION LIMITS for the member
            is_valid, error_msg = validate_event_registration_limit(register_number, team.event)
            if not is_valid:
                logger.warning(f"Event registration limit validation failed for member {register_number}: {error_msg}")
                messages.error(request, error_msg)
                return render(request, 'core/add_team_member.html', {'team': team})
            
            # Find registration by register number
            member_registration = Registration.objects.filter(register_number=register_number).first()
            
            if not member_registration:
                messages.error(request, f'Register number {register_number} not found.')
            elif member_registration.event != team.event:
                messages.error(request, f'{member_registration.full_name} is not registered for this event.')
            elif TeamMember.objects.filter(team=team, registration=member_registration).exists():
                messages.error(request, 'This member is already in the team.')
            else:
                # Add member with pending status
                TeamMember.objects.create(
                    team=team,
                    registration=member_registration,
                    status='pending'
                )
                
                messages.success(request, f'{member_registration.full_name} has been invited to the team.')
                return redirect('view_team', team_id=team_id)
        
        except Exception as e:
            messages.error(request, f'Error adding team member: {str(e)}')
    
    context = {'team': team}
    return render(request, 'core/add_team_member.html', context)


@team_login_required

@team_login_required
def edit_team_member(request, team_id, member_id):
    """Edit team member details including register number"""
    team = get_object_or_404(Team, id=team_id)
    team_member = get_object_or_404(TeamMember, id=member_id, team=team)
    
    # Verify team matches session
    if team.id != request.session.get('team_id'):
        messages.error(request, 'Team access denied.')
        return redirect('team_login')
    
    # Check authorization - only team leader or admin
    is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff)
    is_leader = False
    
    if not is_admin:
        if request.user.is_authenticated:
            is_leader = team.created_by and team.created_by.user == request.user
        
        if not is_leader and request.user.is_authenticated:
            messages.error(request, 'You do not have permission to manage this team.')
            return redirect('team_dashboard')
    
    if request.method == 'POST':
        # Update member details
        register_number = request.POST.get('register_number', '').strip().upper()
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        department = request.POST.get('department', '').strip()
        year = request.POST.get('year', '').strip()
        status = request.POST.get('status', '').strip()
        
        if all([register_number, full_name, email, phone_number, department, year]):
            registration = team_member.registration
            
            # Check if new register number already exists for this event (excluding current member)
            if register_number != registration.register_number:
                duplicate_check = Registration.objects.filter(
                    register_number=register_number,
                    event=team.event
                ).exclude(id=registration.id).first()
                
                if duplicate_check:
                    messages.error(request, f'❌ Register number {register_number} already exists for this event.')
                    context = {
                        'team': team,
                        'team_member': team_member,
                        'member': registration,
                        'statuses': ['pending', 'joined', 'declined'],
                    }
                    return render(request, 'core/edit_team_member.html', context)
                
                # ✅ VALIDATE EVENT REGISTRATION LIMITS for the new register number
                is_valid, error_msg = validate_event_registration_limit(
                    register_number, 
                    team.event,
                    exclude_registration_id=registration.id
                )
                if not is_valid:
                    logger.warning(f"Event registration limit validation failed for member {register_number}: {error_msg}")
                    messages.error(request, error_msg)
                    context = {
                        'team': team,
                        'team_member': team_member,
                        'member': registration,
                        'statuses': ['pending', 'joined', 'declined'],
                    }
                    return render(request, 'core/edit_team_member.html', context)
            
            # Update all registration details
            registration.register_number = register_number
            registration.full_name = full_name
            registration.email = email
            registration.phone_number = phone_number
            registration.department = department
            registration.year = year
            registration.save()
            
            if status in ['pending', 'joined', 'declined']:
                team_member.status = status
                team_member.save()
            
            messages.success(request, f'✅ {full_name} has been updated successfully! Register Number: {register_number}')
            return redirect('team_dashboard')
        else:
            messages.error(request, 'All fields are required.')
    
    context = {
        'team': team,
        'team_member': team_member,
        'member': team_member.registration,
        'statuses': ['pending', 'joined', 'declined'],
    }
    return render(request, 'core/edit_team_member.html', context)


def remove_team_member(request, team_id, member_id):
    """Remove a team member using Registration database"""
    team = get_object_or_404(Team, id=team_id)
    team_member = get_object_or_404(TeamMember, id=member_id, team=team)
    
    # Verify team matches session
    if team.id != request.session.get('team_id'):
        messages.error(request, 'Team access denied.')
        return redirect('team_login')
    
    # Check authorization
    is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff)
    is_leader = False
    
    if not is_admin:
        # Check if user created this team (if logged in)
        if request.user.is_authenticated:
            is_leader = team.created_by and team.created_by.user == request.user
        
        # Allow access to team if logged in via team_login
        if not is_leader and request.user.is_authenticated:
            messages.error(request, 'You do not have permission to manage this team.')
            return redirect('team_dashboard')
    
    if request.method == 'POST':
        member_name = team_member.registration.full_name
        team_member.delete()
        messages.success(request, f'{member_name} has been removed from the team.')
        return redirect('view_team', team_id=team_id)
    
    context = {'team': team, 'team_member': team_member}
    return render(request, 'core/confirm_remove_member.html', context)


def accept_team_invite(request, team_id):
    """Accept invitation to join a team"""
    team = get_object_or_404(Team, id=team_id)
    
    if not request.user.is_authenticated:
        messages.error(request, 'Please login first.')
        return redirect('team_login')
    
    try:
        # Get user's registration in this team
        user_registrations = Registration.objects.filter(user=request.user, event=team.event)
        team_member = TeamMember.objects.filter(team=team, registration__in=user_registrations).first()
        
        if not team_member:
            messages.error(request, 'No pending invitation found.')
            return redirect('home')
        
        if team_member.status == 'joined':
            messages.info(request, 'You are already a member of this team.')
        elif team_member.status == 'declined':
            messages.error(request, 'You declined this invitation.')
        else:  # pending
            # Update status to joined
            team_member.status = 'joined'
            team_member.joined_at = timezone.now()
            team_member.save()
            messages.success(request, f'You have joined the team "{team.name}"!')
        
        return redirect('view_team', team_id=team_id)
    
    except Exception as e:
        messages.error(request, f'Error accepting invitation: {str(e)}')
        return redirect('home')


def decline_team_invite(request, team_id):
    """Decline invitation to join a team"""
    team = get_object_or_404(Team, id=team_id)
    
    if not request.user.is_authenticated:
        messages.error(request, 'Please login first.')
        return redirect('team_login')
    
    try:
        # Get user's registration in this team
        user_registrations = Registration.objects.filter(user=request.user, event=team.event)
        team_member = TeamMember.objects.filter(team=team, registration__in=user_registrations).first()
        
        if not team_member:
            messages.error(request, 'No pending invitation found.')
            return redirect('home')
        
        if team_member.status != 'pending':
            messages.error(request, 'You cannot decline a non-pending invitation.')
        else:
            team_member.status = 'declined'
            team_member.save()
            messages.success(request, f'You have declined the invitation from "{team.name}".')
        
        return redirect('home')
    
    except Exception as e:
        messages.error(request, f'Error declining invitation: {str(e)}')
        return redirect('home')


# ============ TEAM LOGIN SYSTEM ============

def team_login(request):
    """Team login page - Verify team using only team name and password"""
    from django.contrib.auth.hashers import check_password
    from .models import Team, Registration
    
    # Check if team is already logged in (session-based)
    if 'team_id' in request.session and request.session.get('team_id'):
        # Verify the team still exists
        try:
            team = Team.objects.get(id=request.session.get('team_id'))
            return redirect('team_dashboard')
        except Team.DoesNotExist:
            # Clear invalid session
            if 'team_id' in request.session:
                del request.session['team_id']
            if 'team_name' in request.session:
                del request.session['team_name']
            if 'team_logged_in' in request.session:
                del request.session['team_logged_in']
    
    if request.method == 'POST':
        team_name = request.POST.get('team_name', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not team_name:
            messages.error(request, 'Please enter team name.')
        elif not password:
            messages.error(request, 'Please enter team password.')
        else:
            try:
                # Try exact match first, then case-insensitive
                try:
                    team = Team.objects.get(name=team_name)
                except Team.DoesNotExist:
                    team = Team.objects.get(name__iexact=team_name)
                
                authenticated = False
                logger.info(f"[TEAM_LOGIN] Team found: {team.name}, checking password...")
                logger.info(f"[TEAM_LOGIN] Team.password exists: {bool(team.password)}")
                
                # Check password from multiple sources
                # 1. Check Team.password (original)
                if team.password:
                    is_valid = check_password(password, team.password)
                    logger.info(f"[TEAM_LOGIN] Team.password check result: {is_valid}")
                    if is_valid:
                        authenticated = True
                
                # 2. Check Registration.team_password (synced from Registration dataset)
                if not authenticated:
                    registrations_in_team = Registration.objects.filter(team=team, team_password__isnull=False)
                    logger.info(f"[TEAM_LOGIN] Found {registrations_in_team.count()} registrations with team_password")
                    for registration in registrations_in_team:
                        if registration.team_password:
                            is_valid = check_password(password, registration.team_password)
                            logger.info(f"[TEAM_LOGIN] Registration team_password check result: {is_valid}")
                            if is_valid:
                                authenticated = True
                                break
                
                if authenticated:
                    # Store team session
                    request.session['team_id'] = team.id
                    request.session['team_name'] = team.name
                    request.session['team_logged_in'] = True
                    request.session.set_expiry(86400)  # 24 hour session
                    messages.success(request, f'Welcome to {team.name}!')
                    logger.info(f"[TEAM_LOGIN] Successfully authenticated: {team.name}")
                    return redirect('team_dashboard')
                else:
                    logger.warning(f"[TEAM_LOGIN] Authentication failed for team: {team.name}")
                    messages.error(request, 'Invalid team password. Please try again.')
                    
            except Team.DoesNotExist:
                logger.warning(f"[TEAM_LOGIN] Team not found: {team_name}")
                messages.error(request, 'Team not found. Please check team name.')
            except Exception as e:
                logger.error(f"[TEAM_LOGIN] Error during login: {str(e)}")
                messages.error(request, 'An error occurred. Please try again.')
    
    return render(request, 'core/team_login.html', {})


def team_logout(request):
    """Team logout - Clear team session"""
    team_name = request.session.get('team_name', 'Team')
    if 'team_id' in request.session:
        del request.session['team_id']
    if 'team_name' in request.session:
        del request.session['team_name']
    if 'team_logged_in' in request.session:
        del request.session['team_logged_in']
    
    messages.success(request, f'{team_name} has been logged out successfully.')
    return redirect('team_login')




@team_login_required
def team_dashboard(request):
    """Team dashboard - Only team leader can access their team's dashboard"""
    team_id = request.session.get('team_id')
    
    # Redirect to login if not logged in via team
    if not team_id:
        messages.error(request, 'Please log in to your team first.')
        return redirect('team_login')
    
    try:
        team = Team.objects.select_related('event', 'created_by').get(id=team_id)
    except Team.DoesNotExist:
        messages.error(request, 'Team not found. Please log in again.')
        return redirect('team_login')
    
    # Check if current user is admin (can access any team)
    is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff)
    
    # Check if current user is team lead (based on session team_id, which means they're logged in as a team)
    # For session-based team login, we consider them team lead
    is_team_lead = True  # If they have team_id in session, they're authorized
    
    # Handle edit/delete member actions (only for team lead or admin)
    if request.method == 'POST':
        action = request.POST.get('action')
        member_id = request.POST.get('member_id')
        
        if action == 'approve_member':
            try:
                team_member = TeamMember.objects.get(id=member_id, team=team)
                team_member.status = 'joined'
                team_member.joined_at = timezone.now()
                team_member.save()
                messages.success(request, f'{team_member.registration.full_name} has been approved!')
            except TeamMember.DoesNotExist:
                messages.error(request, 'Member not found.')
        
        elif action == 'remove_member':
            try:
                team_member = TeamMember.objects.get(id=member_id, team=team)
                if team_member.registration == team.created_by:
                    messages.error(request, 'Cannot remove team leader.')
                else:
                    member_name = team_member.registration.full_name
                    team_member.delete()
                    messages.success(request, f'{member_name} removed from team.')
            except TeamMember.DoesNotExist:
                messages.error(request, 'Member not found.')
        
        elif action == 'change_status':
            try:
                team_member = TeamMember.objects.get(id=member_id, team=team)
                new_status = request.POST.get('status')
                if new_status in ['pending', 'joined', 'declined']:
                    team_member.status = new_status
                    team_member.save()
                    messages.success(request, f'Member status updated to {new_status}.')
            except TeamMember.DoesNotExist:
                messages.error(request, 'Member not found.')
    
    # Get team members from TeamMember table (with registrations)
    team_members = team.members.select_related('registration', 'registration__event').all()
    
    # Get team registrations from Registration table (primary source)
    registrations = Registration.objects.filter(team=team).select_related('event')
    
    # Parse registration JSON data for team members
    import json
    team_members_from_registration = []
    
    if team.created_by and team.created_by.team_members:
        try:
            # team_members is now an IntegerField (count), not JSON
            # Skip JSON parsing since it's just a count now
            if isinstance(team.created_by.team_members, int):
                # Just a count, skip JSON parsing
                pass
            else:
                # Try to parse as JSON for backward compatibility
                members_json = json.loads(team.created_by.team_members)
                if isinstance(members_json, dict):
                    if 'team_lead' in members_json:
                        team_members_from_registration.append({
                            'data': members_json['team_lead'],
                            'role': 'Team Lead',
                            'source': 'registration'
                        })
                    if 'team_members' in members_json:
                        for member in members_json['team_members']:
                            team_members_from_registration.append({
                                'data': member,
                                'role': 'Member',
                                'source': 'registration'
                            })
                elif isinstance(members_json, list):
                    for member in members_json:
                        team_members_from_registration.append({
                            'data': member,
                            'role': 'Member',
                            'source': 'registration'
                        })
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    
    context = {
        'team': team,
        'team_members': team_members,
        'registrations': registrations,
        'team_members_from_registration': team_members_from_registration,
        'member_count': team.member_count,
        'pending_count': team.pending_count,
        'total_count': team.total_count,
        'registration_count': registrations.count(),
        'is_team_lead': is_team_lead,
        'is_admin': is_admin,
        'can_manage_members': is_team_lead or is_admin,
    }
    return render(request, 'core/team_dashboard.html', context)


# Chatbot Training Views (Admin Only)
@login_required(login_url='core:login')
def chatbot_training(request):
    """Display and manage chatbot training data - Admin only"""
    # Check if user is admin
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('core:home')
    
    # Handle form submission for new training pair
    if request.method == 'POST' and 'question' in request.POST:
        question = request.POST.get('question', '').strip()
        answer = request.POST.get('answer', '').strip()
        intent = request.POST.get('intent', '').strip() or None
        keywords = request.POST.get('keywords', '').strip() or None
        is_active = request.POST.get('is_active') == 'on'
        
        if question and answer:
            try:
                ChatbotTraining.objects.create(
                    question=question,
                    answer=answer,
                    intent=intent,
                    keywords=keywords,
                    is_active=is_active,
                    created_by=request.user
                )
                messages.success(request, "✅ Training pair added successfully!")
                return redirect('core:chatbot_training')
            except Exception as e:
                messages.error(request, f"❌ Error adding training pair: {str(e)}")
        else:
            messages.error(request, "❌ Please fill in both question and answer fields.")
    
    # Get all training pairs
    training_pairs = ChatbotTraining.objects.all()
    
    context = {
        'training_pairs': training_pairs,
        'total_active': training_pairs.filter(is_active=True).count(),
        'total_inactive': training_pairs.filter(is_active=False).count(),
    }
    
    return render(request, 'core/chatbot_training.html', context)


@login_required(login_url='core:login')
def edit_training(request, training_id):
    """Edit a training pair - Admin only"""
    # Check if user is admin
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('core:home')
    
    training = get_object_or_404(ChatbotTraining, id=training_id)
    
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        answer = request.POST.get('answer', '').strip()
        intent = request.POST.get('intent', '').strip() or None
        keywords = request.POST.get('keywords', '').strip() or None
        is_active = request.POST.get('is_active') == 'on'
        
        if question and answer:
            try:
                training.question = question
                training.answer = answer
                training.intent = intent
                training.keywords = keywords
                training.is_active = is_active
                training.save()
                messages.success(request, "✅ Training pair updated successfully!")
                return redirect('core:chatbot_training')
            except Exception as e:
                messages.error(request, f"❌ Error updating training pair: {str(e)}")
        else:
            messages.error(request, "❌ Please fill in both question and answer fields.")
    
    context = {
        'training': training,
        'is_edit': True,
    }
    
    return render(request, 'core/chatbot_training_edit.html', context)


@login_required(login_url='core:login')
def delete_training(request, training_id):
    """Delete a training pair - Admin only"""
    # Check if user is admin
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('core:home')
    
    training = get_object_or_404(ChatbotTraining, id=training_id)
    question = training.question[:50]
    
    try:
        training.delete()
        messages.success(request, f"✅ Training pair deleted: '{question}...'")
    except Exception as e:
        messages.error(request, f"❌ Error deleting training pair: {str(e)}")
    
    return redirect('core:chatbot_training')
