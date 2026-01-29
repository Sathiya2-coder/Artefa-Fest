from django import forms
from django.contrib.auth.models import User
from .models import Registration, ContactMessage, Event, Coordinator

class EventForm(forms.ModelForm):
    """Form for creating and editing events with time fields"""
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control',
            'required': 'required'
        }),
        required=True,
        label='Start Time'
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control',
            'required': 'required'
        }),
        required=True,
        label='End Time'
    )
    event_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'required': 'required'
        }),
        required=True,
        label='Event Date'
    )
    
    class Meta:
        model = Event
        fields = ['name', 'slug', 'description', 'event_type', 'icon_class', 
                  'duration', 'venue', 'start_time', 'end_time', 'event_date', 
                  'is_team_event', 'min_team_size', 'max_team_size']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'icon_class': forms.TextInput(attrs={'class': 'form-control'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 7 hours'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Lab 1, Room 101'}),
            'is_team_event': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_team_size': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_team_size': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('Start time must be before end time.')
        
        return cleaned_data

class RegistrationForm(forms.ModelForm):
    events = forms.ModelChoiceField(
        queryset=Event.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select form-control-lg',
            'id': 'id_events',
            'required': 'required'
        }),
        required=True,
        label='Select Competition',
        empty_label='-- Choose a Competition --'
    )
    
    team_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Phoenix Team',
            'id': 'id_team_name',
            'autocomplete': 'off'
        }),
        help_text="Required only for team events"
    )
    
    team_member_count = forms.IntegerField(
        required=False,
        min_value=0,  # Allow 0 for non-team events
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Number of team members',
            'id': 'id_team_member_count',
            'min': '0'
        }),
        help_text="Number of team members (including yourself)"
    )
    
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password to secure registration (optional)',
            'autocomplete': 'new-password'
        }),
        help_text="Set a password for your account (required for team events, optional for individual registration)"
    )
    
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password',
            'autocomplete': 'new-password'
        }),
        help_text="Re-enter password to confirm"
    )
    
    team_members = forms.CharField(
        widget=forms.HiddenInput(attrs={
            'id': 'id_team_members'
        }),
        required=False,
        help_text="Team member details (stored as JSON)"
    )
    
    def __init__(self, *args, **kwargs):
        """Initialize form with fresh event data from database - OPTIMIZED"""
        super().__init__(*args, **kwargs)
        # Optimize queryset: only fetch necessary fields to reduce database query time
        self.fields['events'].queryset = Event.objects.only(
            'id', 'name', 'event_type', 'is_team_event', 'min_team_size', 'max_team_size'
        )
    
    class Meta:
        model = Registration
        fields = [
            'full_name', 'register_number', 'year', 
            'department', 'phone_number', 'email'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., John Doe',
                'required': 'required',
                'autocomplete': 'name'
            }),
            'register_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 21AID001',
                'required': 'required',
                'autocomplete': 'off'
            }),
            'year': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'autocomplete': 'off'
            }),
            'department': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'autocomplete': 'off'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'tel',
                'placeholder': 'e.g., 9876543210',
                'required': 'required',
                'autocomplete': 'tel'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., your.email@college.ac.in',
                'required': 'required',
                'autocomplete': 'email'
            }),
        }
    
    def clean_register_number(self):
        reg_number = self.cleaned_data['register_number'].strip().upper()
        # Validation will be done in the view for better error handling
        return reg_number
    
    def clean(self):
        cleaned_data = super().clean()
        event = cleaned_data.get('events')
        team_name = cleaned_data.get('team_name', '').strip()
        team_member_count = cleaned_data.get('team_member_count')
        password = cleaned_data.get('password', '')
        confirm_password = cleaned_data.get('confirm_password', '')
        
        # Password validation - if one is provided, both must match
        if password or confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match.')
        
        # For team events: team fields are ONLY required if creating a team (team_name provided)
        # Solo members can register for team events without providing team info
        if event and event.is_team_event and team_name:
            # Team fields are required ONLY when creating a team (team_name is provided)
            if not password:
                self.add_error('password', 'Password is required when creating a team.')
            # For team events with team, team_member_count can be 0 (just the team lead)
            if team_member_count is not None and team_member_count < 0:
                self.add_error('team_member_count', 'Team member count cannot be negative')
            
            # ✅ ENFORCE MAXIMUM TEAM SIZE
            if team_member_count is not None and team_member_count > event.max_team_size:
                self.add_error('team_member_count', 
                    f'Team member count cannot exceed {event.max_team_size} members for {event.name}')
            
            # ✅ ENFORCE MINIMUM TEAM SIZE (if creating a team)
            if team_member_count is not None and team_member_count < event.min_team_size:
                self.add_error('team_member_count',
                    f'Team must have at least {event.min_team_size} members for {event.name}')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to ensure register_number is uppercase"""
        instance = super().save(commit=False)
        # Ensure register_number is uppercase
        instance.register_number = self.cleaned_data['register_number'].strip().upper()
        if commit:
            instance.save()
        return instance

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
        }

class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email',
            'required': 'required'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'required': 'required'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if username and password:
            # Check if user exists by username or email
            user = User.objects.filter(username=username).first() or \
                   User.objects.filter(email=username).first()
            
            if user and user.check_password(password):
                cleaned_data['user'] = user
            else:
                raise forms.ValidationError('Invalid username/email or password.')
        
        return cleaned_data

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'required': 'required'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No account found with this email address.')
        return email


class CoordinatorForm(forms.ModelForm):
    """Form for adding and editing event coordinators"""
    
    class Meta:
        model = Coordinator
        fields = ['event', 'name', 'register_number', 'year', 'event_type']
        widgets = {
            'event': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Coordinator Name'}),
            'register_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2317029'}),
            'year': forms.Select(attrs={'class': 'form-select'}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
        }

class SendAlertForm(forms.Form):
    """Form for sending alert messages to participants"""
    recipient_type = forms.ChoiceField(
        choices=[
            ('all', 'All Participants'),
            ('event', 'Participants of Specific Event'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Send to'
    )
    event = forms.ModelChoiceField(
        queryset=Event.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Select Event (if applicable)'
    )
    subject = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Subject'
        }),
        label='Subject'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Type your alert message here...'
        }),
        label='Message'
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'image-upload'
        }),
        label='Attach Image (Optional)',
        help_text='Supported: JPG, PNG, GIF, WebP (Max 5MB)'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        recipient_type = cleaned_data.get('recipient_type')
        event = cleaned_data.get('event')
        image = cleaned_data.get('image')
        
        if recipient_type == 'event' and not event:
            raise forms.ValidationError("Please select an event when sending to event participants.")
        
        if image and image.size > 5 * 1024 * 1024:  # 5MB limit
            raise forms.ValidationError("Image size must not exceed 5MB.")
        
        return cleaned_data


class TeamLoginForm(forms.Form):
    """Form for team login using team name and password"""
    team_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your team name',
            'required': 'required',
            'autofocus': 'autofocus'
        }),
        label='Team Name'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your team password',
            'required': 'required'
        }),
        label='Team Password'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        team_name = cleaned_data.get('team_name')
        password = cleaned_data.get('password')
        
        if team_name and password:
            from .models import Team
            try:
                team = Team.objects.get(name=team_name)
                # Verify password (check_password is from User model, we'll use a simple check)
                if team.password and team.password == password:
                    cleaned_data['team'] = team
                else:
                    raise forms.ValidationError('Invalid team name or password.')
            except Team.DoesNotExist:
                raise forms.ValidationError('Team not found. Please check the team name.')
        
        return cleaned_data
