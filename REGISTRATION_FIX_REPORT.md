# Event Registration System - Bug Fix Report

## Problem Statement

Users who had successfully registered for ONE technical event were being rejected when attempting to register for ONE non-technical event. The system error was:

**"Registration number is already registered"**

This error message incorrectly prevented valid registrations (1 technical + 1 non-technical).

---

## Root Cause Analysis

### Issue Location
**File**: `core/views.py`, **Lines**: 391-399 (in the `register` view)

### Problematic Code
```python
# ❌ WRONG - This checks if register_number exists in ANY event
if Registration.objects.filter(register_number__iexact=register_number).exists():
    logger.warning(f"Registration number {register_number} already exists")
    form.add_error('register_number', f'Registration number "{register_number}" is already registered. Please use a different registration number or login to your account.')
    return render(request, 'core/register.html', {'form': form})

# ❌ WRONG - This checks if email exists in ANY event
if Registration.objects.filter(email__iexact=email).exists():
    logger.warning(f"Email {email} already exists")
    form.add_error('email', f'Email "{email}" is already registered. Please use a different email or login to your account.')
    return render(request, 'core/register.html', {'form': form})
```

### Why This Was Wrong

The code was checking if a register_number existed in the Registration table **at all**, but this prevents users from:
- Registering for BOTH a technical AND non-technical event
- Having multiple registrations across different event types

The validation should ONLY block:
- Same register_number registering for the SAME event twice (duplicate)
- Same register_number registering for 2+ technical events
- Same register_number registering for 2+ non-technical events

---

## Solution Implemented

### Fixed Code
```python
# ✅ CORRECT - Check if event is provided
selected_event = form.cleaned_data.get('events')
if not selected_event:
    raise ValueError("Event selection is required")

# ✅ CORRECT - Only check for DUPLICATE registration of same event
existing_reg_for_same_event = Registration.objects.filter(
    register_number__iexact=register_number,
    event=selected_event
).exists()

if existing_reg_for_same_event:
    logger.warning(f"Registration number {register_number} already registered for event {selected_event.name}")
    form.add_error('register_number', f'Registration number "{register_number}" is already registered for this event.')
    return render(request, 'core/register.html', {'form': form})
```

### How This Works

1. **Get the selected event early** in the validation process
2. **Check only for duplicate registrations** (same register_number + same event)
3. **Allow cross-type registration** (1 technical + 1 non-technical)
4. **Let the `validate_event_registration_limit()` function handle type limits**

---

## Validation Flow

Now the registration process works in this order:

```
1. Check if duplicate for THIS event (prevent re-registration)
   ↓
2. Create/get user account
   ↓
3. Call validate_event_registration_limit()
   ↓
4. Ensure they don't have 2+ technical events
   ↓
5. Ensure they don't have 2+ non-technical events
   ↓
6. Allow registration for 1 technical + 1 non-technical
```

---

## Example Scenarios

### ✅ ALLOWED (Now Works Correctly)

| Register | Event 1 | Event 2 | Result |
|----------|---------|---------|--------|
| ABC001 | Coding Contest (Technical) | Quiz (Non-Tech) | ✅ ALLOWED |
| ABC002 | Hackathon (Technical) | Gaming (Non-Tech) | ✅ ALLOWED |
| ABC003 | Web Dev (Technical) | Debate (Non-Tech) | ✅ ALLOWED |

### ❌ BLOCKED (Correct Behavior)

| Register | Event 1 | Event 2 | Reason |
|----------|---------|---------|--------|
| ABC001 | Coding Contest (Tech) | Coding Contest (Tech) | Same event - duplicate |
| ABC002 | Hackathon (Tech) | Web Dev (Tech) | 2 Technical events - limit |
| ABC003 | Quiz (Non-Tech) | Gaming (Non-Tech) | 2 Non-Technical - limit |

---

## Files Modified

1. **core/views.py** - `register()` view
   - Lines 387-408: Fixed registration duplicate checking logic
   - Removed email uniqueness validation (allows cross-event email reuse)
   - Added early event selection for validation
   - Delegated event-type limit checking to `validate_event_registration_limit()`

---

## Other Views Already Correct

These views already had proper validation:
- ✅ `create_team()` - Validates limits before team creation
- ✅ `team_add_members()` - Validates each member's registration limits
- ✅ `add_team_member()` - Validates member registration limits

---

## Database Constraints

The Registration model has:
```python
class Meta:
    unique_together = ['register_number', 'event']
```

This unique constraint:
- ✅ Prevents duplicate registrations for same event
- ✅ Allows same register_number for different events
- ✅ Works perfectly with the fixed validation logic

---

## Testing the Fix

### Test Case 1: Register for Technical Event
1. User registers as ABC001 for "Coding Contest" (Technical)
2. ✅ Registration succeeds

### Test Case 2: Register for Non-Technical Event
1. Same user (ABC001) tries to register for "Quiz" (Non-Technical)
2. ✅ Should now succeed (previously failed)
3. Result: ABC001 is registered for 1 technical + 1 non-technical ✅

### Test Case 3: Try to Register for Same Type Again
1. User ABC001 tries to register for another Technical event (e.g., "Hackathon")
2. ❌ Should be blocked with error: "Register number is already registered for one technical event"
3. This is correct behavior ✅

---

## Performance Impact

- **Minimal overhead**: Adds one database query to check for duplicate same-event registration
- **Already validated**: The `validate_event_registration_limit()` function was already being called and does the heavy lifting
- **No schema changes**: Uses existing unique_together constraint

---

## Related Training Data

10 new chatbot training Q&A entries have been added to explain this rule:
- "What is the rule for event registration?"
- "Can I register for two technical events?"
- "Can I register for multiple non-technical events?"
- "How many events can I participate in?"
- And 6 more covering various aspects of the rule

These training entries help users understand WHY they might get an error and what they can do instead.

---

## Summary

✅ **FIXED**: Users can now register for 1 technical + 1 non-technical event  
✅ **ENFORCED**: System still blocks 2+ of the same event type  
✅ **VALIDATED**: Django check shows no errors  
✅ **DOCUMENTED**: Added training data for chatbot support  

The registration system now works as designed!
