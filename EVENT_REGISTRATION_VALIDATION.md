# Event Registration Validation System

## Overview
This document describes the validation system that ensures each register number can only register for:
- **ONE technical event**
- **ONE non-technical event**
- **NOT two or more of the same type**

## Implementation Details

### 1. Validation Helper Function
**Location**: `core/views.py` (lines 27-52)

```python
def validate_event_registration_limit(register_number, new_event=None, exclude_registration_id=None):
```

**Purpose**: 
- Validates that a register number doesn't exceed event type limits
- Checks both technical and non-technical event registrations
- Prevents duplicate registrations of the same event type

**Parameters**:
- `register_number`: The registration number to validate
- `new_event`: The new event the user is trying to register for (Event object)
- `exclude_registration_id`: Registration ID to exclude from check (for edit operations)

**Returns**: 
- `tuple`: `(is_valid: bool, error_message: str or None)`

---

## Validation Points

### 1. **Registration View** (`register` function)
**Location**: Line ~370

When a user submits the registration form:
- The system validates the event registration limit
- Error message shown: `"❌ Register number [REG_NO] is already registered for one [TYPE] event. Cannot register for another [TYPE] event."`
- User is redirected back to the registration form if validation fails

```python
# ✅ VALIDATE EVENT REGISTRATION LIMITS
is_valid, error_msg = validate_event_registration_limit(register_number, selected_event)
if not is_valid:
    logger.warning(f"Event registration limit validation failed: {error_msg}")
    messages.error(request, error_msg)
    return render(request, 'core/register.html', {'form': form})
```

---

### 2. **Create Team View** (`create_team` function)
**Location**: Line ~1966

When a user creates a team for a team event:
- The system validates that the team lead hasn't already registered for another event of the same type
- Error message shown: `"❌ Register number [REG_NO] is already registered for one [TYPE] event. Cannot register for another [TYPE] event."`
- Team creation is blocked if validation fails

```python
# ✅ VALIDATE EVENT REGISTRATION LIMITS before creating team
if registration:
    is_valid, error_msg = validate_event_registration_limit(registration.register_number, event)
    if not is_valid:
        logger.warning(f"Event registration limit validation failed: {error_msg}")
        messages.error(request, error_msg)
        return render(request, 'core/create_team.html', {'event': event})
```

---

### 3. **Team Add Members View** (`team_add_members` function)
**Location**: Line ~2117

When adding members to a team:
- The system validates each new member's event registration limit
- Error message shown: `"❌ Register number [REG_NO] is already registered for one [TYPE] event. Cannot register for another [TYPE] event."`
- Member addition is blocked if validation fails
- Validation occurs BEFORE checking team capacity

```python
# ✅ VALIDATE EVENT REGISTRATION LIMITS for the member
is_valid, error_msg = validate_event_registration_limit(register_number, team.event)
if not is_valid:
    logger.warning(f"Event registration limit validation failed for member {register_number}: {error_msg}")
    messages.error(request, error_msg)
else:
    # Continue with member addition...
```

---

### 4. **Add Team Member View** (`add_team_member` function)
**Location**: Line ~2260

When adding a single team member:
- The system validates the member's event registration limit
- Error message shown: `"❌ Register number [REG_NO] is already registered for one [TYPE] event. Cannot register for another [TYPE] event."`
- Member addition is blocked if validation fails

```python
# ✅ VALIDATE EVENT REGISTRATION LIMITS for the member
is_valid, error_msg = validate_event_registration_limit(register_number, team.event)
if not is_valid:
    logger.warning(f"Event registration limit validation failed for member {register_number}: {error_msg}")
    messages.error(request, error_msg)
    return render(request, 'core/add_team_member.html', {'team': team})
```

---

## Validation Logic

The validation function works as follows:

1. **Fetch all existing registrations** for the given register number
2. **Count registrations by event type**:
   - `technical_count` = number of technical events registered
   - `non_technical_count` = number of non-technical events registered
3. **Check new event type**:
   - If new event is **technical** and `technical_count >= 1` → REJECT
   - If new event is **non-technical** and `non_technical_count >= 1` → REJECT
4. **Allow** if validation passes

---

## Example Scenarios

### ✅ Allowed Scenarios:
1. Register number registers for 1 technical event → ✅ Allowed
2. Register number registers for 1 non-technical event → ✅ Allowed  
3. Register number registers for 1 technical + 1 non-technical event → ✅ Allowed

### ❌ Blocked Scenarios:
1. Register number tries to register for 2 technical events → ❌ Blocked
2. Register number tries to register for 2 non-technical events → ❌ Blocked
3. Register number (already in 1 technical) tries to join team for another technical event → ❌ Blocked
4. Register number (already in 1 non-technical) tries to add member to team for another non-technical event → ❌ Blocked

---

## Error Messages

The system provides clear, user-friendly error messages:

```
❌ Register number "CS001" is already registered for one technical event. 
Cannot register for another technical event.
```

```
❌ Register number "IT015" is already registered for one non-technical event. 
Cannot register for another non-technical event.
```

---

## Database Queries

The validation system uses efficient Django ORM queries:

```python
# Get all registrations for the register number
registrations = Registration.objects.filter(register_number__iexact=register_number)\
    .select_related('event')\
    .exclude(id=exclude_registration_id)

# Count by event type
technical_count = sum(1 for reg in registrations if reg.event.event_type == 'technical')
non_technical_count = sum(1 for reg in registrations if reg.event.event_type == 'non-technical')
```

---

## Logging

All validation attempts are logged for debugging and audit purposes:

```python
# Success
logger.info(f"Event registration validation passed for {register_number}")

# Failure
logger.warning(f"Event registration limit validation failed: {error_message}")
```

---

## Testing Recommendations

### Test Cases:

1. **Single Registration**: User registers for one technical event
   - Expected: ✅ Success

2. **Valid Multiple Events**: User registers for one technical + one non-technical
   - Expected: ✅ Success

3. **Duplicate Technical**: User tries to register for second technical event
   - Expected: ❌ Blocked with error message

4. **Duplicate Non-Technical**: User tries to register for second non-technical event
   - Expected: ❌ Blocked with error message

5. **Team Creation**: User creates a team for event with limit violation
   - Expected: ❌ Team creation blocked

6. **Add Members**: Team lead tries to add member who violates limits
   - Expected: ❌ Member addition blocked with error message

---

## Files Modified

- `core/views.py`:
  - Added `validate_event_registration_limit()` function
  - Updated `register()` view
  - Updated `create_team()` view
  - Updated `team_add_members()` view
  - Updated `add_team_member()` view

---

## Notes

- Validation is **case-insensitive** for register numbers (uses `__iexact`)
- Validation works with both existing registrations and new team member additions
- The system is **transactional** - registrations are rolled back if validation fails
- All validation occurs **before** creating/modifying database records
- Error messages are user-friendly and informative

