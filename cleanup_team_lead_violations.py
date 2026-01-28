"""
Script to cleanup registration violations where a person is:
1. Team lead of one technical/non-technical event
2. AND member of another technical/non-technical event of same type

This script will remove such members from the TeamMember table.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artifa_fest.settings')
django.setup()

from core.models import Registration, TeamMember, Event
from django.db.models import Q

print("="*70)
print("REGISTRATION VIOLATIONS CLEANUP")
print("="*70)

# Find all registrations where a person is team lead
team_leads = Registration.objects.filter(is_team_lead=True).select_related('event')

violations_found = 0
violations_fixed = 0

print(f"\nScanning {team_leads.count()} team leads for violations...\n")

for team_lead_reg in team_leads:
    register_number = team_lead_reg.register_number
    team_lead_event = team_lead_reg.event
    team_lead_event_type = team_lead_event.event_type
    
    # Find all other registrations for this person
    other_registrations = Registration.objects.filter(
        register_number__iexact=register_number
    ).exclude(
        id=team_lead_reg.id
    ).select_related('event')
    
    for other_reg in other_registrations:
        # Check if the other registration is for same event type
        if other_reg.event.event_type == team_lead_event_type:
            # This is a violation - person is team lead of one technical/non-technical
            # and member of another technical/non-technical
            violations_found += 1
            
            print(f"⚠️  VIOLATION FOUND:")
            print(f"   Register Number: {register_number}")
            print(f"   Team Lead of: {team_lead_event.name} ({team_lead_event_type})")
            print(f"   Also member of: {other_reg.event.name} ({other_reg.event.event_type})")
            
            # Check if this person is in TeamMember table for the other event
            team_members = TeamMember.objects.filter(
                registration=other_reg
            )
            
            if team_members.exists():
                for team_member in team_members:
                    team_name = team_member.team.name
                    team_event = team_member.team.event.name
                    
                    print(f"   ❌ Removing from team: {team_name} ({team_event})")
                    print(f"      TeamMember ID: {team_member.id}")
                    
                    # Delete the TeamMember entry
                    team_member.delete()
                    violations_fixed += 1
                    
                    # Also remove the registration for other event if it's not the team
                    other_reg.delete()
                    print(f"      Deleted Registration ID: {other_reg.id}")
            else:
                # Even if not in TeamMember table, remove the registration
                print(f"   ❌ Deleting registration for: {other_reg.event.name}")
                print(f"      Registration ID: {other_reg.id}")
                other_reg.delete()
                violations_fixed += 1
            
            print()

print("="*70)
print(f"CLEANUP SUMMARY")
print("="*70)
print(f"Total violations found: {violations_found}")
print(f"Total violations fixed: {violations_fixed}")
print(f"Status: {'✅ COMPLETE' if violations_found == violations_fixed else '⚠️  PARTIAL'}")
print("="*70)

# Verify cleanup
print("\nVerifying cleanup...\n")

remaining_violations = 0
for team_lead_reg in Registration.objects.filter(is_team_lead=True).select_related('event'):
    register_number = team_lead_reg.register_number
    team_lead_event_type = team_lead_reg.event.event_type
    
    # Check if person has other registrations of same type
    same_type_regs = Registration.objects.filter(
        register_number__iexact=register_number,
        event__event_type=team_lead_event_type
    ).exclude(id=team_lead_reg.id)
    
    if same_type_regs.exists():
        remaining_violations += 1
        print(f"⚠️  Still a violation: {register_number} - Team lead and member of same type")

if remaining_violations == 0:
    print("✅ No violations detected! Database is clean.")
else:
    print(f"⚠️  {remaining_violations} violations still remain.")

print("\n" + "="*70)
