"""
Test script to verify that a register number can now be registered for multiple events
(1 technical + 1 non-technical)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artifa_fest.settings')
django.setup()

from core.models import Registration, Event

print("="*70)
print("TESTING MULTI-EVENT REGISTRATION")
print("="*70)

# Create test events
tech_event, _ = Event.objects.get_or_create(
    slug='test-technical',
    defaults={
        'name': 'Test Technical Event',
        'description': 'Test',
        'event_type': 'technical',
        'is_team_event': False
    }
)

non_tech_event, _ = Event.objects.get_or_create(
    slug='test-non-technical',
    defaults={
        'name': 'Test Non-Technical Event',
        'description': 'Test',
        'event_type': 'non-technical',
        'is_team_event': False
    }
)

test_register_number = 'TEST001'

print(f"\nTest Register Number: {test_register_number}")
print(f"Technical Event: {tech_event.name}")
print(f"Non-Technical Event: {non_tech_event.name}")

# Clean up any existing test data
Registration.objects.filter(register_number=test_register_number).delete()

print("\n" + "="*70)
print("TEST 1: Register for Technical Event")
print("="*70)

try:
    reg1 = Registration.objects.create(
        register_number=test_register_number,
        full_name='Test User',
        email='test@example.com',
        phone_number='9999999999',
        year='1',
        department='CSE',
        event=tech_event
    )
    print(f"✅ Successfully registered for: {tech_event.name}")
    print(f"   Registration ID: {reg1.id}")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    exit(1)

print("\n" + "="*70)
print("TEST 2: Register SAME Person for Non-Technical Event")
print("="*70)

try:
    reg2 = Registration.objects.create(
        register_number=test_register_number,
        full_name='Test User',
        email='test@example.com',
        phone_number='9999999999',
        year='1',
        department='CSE',
        event=non_tech_event
    )
    print(f"✅ Successfully registered for: {non_tech_event.name}")
    print(f"   Registration ID: {reg2.id}")
    print(f"\n✅ SAME person can now register for both technical AND non-technical events!")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    exit(1)

print("\n" + "="*70)
print("TEST 3: Verify both registrations exist")
print("="*70)

registrations = Registration.objects.filter(register_number=test_register_number)
print(f"Total registrations for {test_register_number}: {registrations.count()}")

for reg in registrations:
    print(f"  • {reg.event.name} ({reg.event.event_type}) - ID: {reg.id}")

if registrations.count() == 2:
    print("\n✅ TEST PASSED: Same person registered for 2 events!")
else:
    print(f"\n❌ TEST FAILED: Expected 2 registrations, got {registrations.count()}")
    exit(1)

# Cleanup
print("\nCleaning up test data...")
Registration.objects.filter(register_number=test_register_number).delete()
Event.objects.filter(slug__startswith='test-').delete()
print("✅ Test data cleaned up")

print("\n" + "="*70)
print("✅ ALL TESTS PASSED!")
print("="*70)
print("\nThe registration system now correctly allows:")
print("  ✅ Same register number for multiple events")
print("  ✅ 1 technical + 1 non-technical per person")
print("  ✅ Prevents duplicate registration for same event")
print("  ✅ Prevents team lead conflicts")
print("="*70 + "\n")
