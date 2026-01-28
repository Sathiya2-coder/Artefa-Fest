"""
Script to safely delete all data from Registration, Team, and TeamMember tables.
This will clear all registration, team, and team member data from the database.

WARNING: This operation is IRREVERSIBLE!
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artifa_fest.settings')
django.setup()

from core.models import Registration, Team, TeamMember
from django.db import transaction

print("="*70)
print("DATA DELETION SCRIPT - REGISTRATION, TEAM, TEAM MEMBERS")
print("="*70)
print("\n⚠️  WARNING: This will DELETE all data from:")
print("   - TeamMember table")
print("   - Team table")
print("   - Registration table")
print("\nThis operation is IRREVERSIBLE!\n")

# Show current counts
print("Current Data Counts:")
print(f"  TeamMembers: {TeamMember.objects.count()}")
print(f"  Teams: {Team.objects.count()}")
print(f"  Registrations: {Registration.objects.count()}")
print()

# Auto-confirm for automated deletion
print("Proceeding with deletion in 3 seconds...")
print("(Override by pressing Ctrl+C)\n")

import time
try:
    time.sleep(3)
except KeyboardInterrupt:
    print("\n❌ Deletion cancelled by user. No data was deleted.")
    exit(0)

print("\n" + "="*70)
print("PROCEEDING WITH DELETION...")
print("="*70 + "\n")

try:
    with transaction.atomic():
        # Delete in order of dependencies
        print("1. Deleting TeamMembers...")
        team_member_count = TeamMember.objects.count()
        TeamMember.objects.all().delete()
        print(f"   ✅ Deleted {team_member_count} TeamMember records")
        
        print("\n2. Deleting Teams...")
        team_count = Team.objects.count()
        Team.objects.all().delete()
        print(f"   ✅ Deleted {team_count} Team records")
        
        print("\n3. Deleting Registrations...")
        registration_count = Registration.objects.count()
        Registration.objects.all().delete()
        print(f"   ✅ Deleted {registration_count} Registration records")
        
        print("\n" + "="*70)
        print("DELETION SUMMARY")
        print("="*70)
        print(f"✅ TeamMembers deleted: {team_member_count}")
        print(f"✅ Teams deleted: {team_count}")
        print(f"✅ Registrations deleted: {registration_count}")
        print("="*70 + "\n")
        
        # Verify deletion
        print("Verifying deletion...\n")
        print("Final Data Counts:")
        print(f"  TeamMembers: {TeamMember.objects.count()}")
        print(f"  Teams: {Team.objects.count()}")
        print(f"  Registrations: {Registration.objects.count()}")
        
        if (TeamMember.objects.count() == 0 and 
            Team.objects.count() == 0 and 
            Registration.objects.count() == 0):
            print("\n✅ All data successfully deleted!")
        else:
            print("\n⚠️  Some data still remains!")

except Exception as e:
    print(f"\n❌ Error during deletion: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
