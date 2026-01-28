"""
Script to insert chatbot training data about event registration rules
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artifa_fest.settings')
django.setup()

from core.models import ChatbotTraining

# Training data for event registration rules
training_data = [
    {
        "question": "What is the rule for event registration?",
        "answer": "The event registration rule is simple: Each participant (identified by register number) can register for ONE technical event AND ONE non-technical event. You CANNOT register for two technical events or two non-technical events.",
        "intent": "registration_rules",
        "keywords": "registration, rule, technical, non-technical, limit, one event"
    },
    {
        "question": "Can I register for two technical events?",
        "answer": "No, you cannot register for two technical events. According to ARTIFA FEST rules, each register number can only participate in ONE technical event. However, you can also register for ONE non-technical event in addition to your technical event.",
        "intent": "registration_rules",
        "keywords": "technical event, two events, limit, restriction"
    },
    {
        "question": "Can I register for multiple non-technical events?",
        "answer": "No, you can only register for ONE non-technical event. Each register number is limited to one technical and one non-technical event. You cannot register for multiple non-technical events.",
        "intent": "registration_rules",
        "keywords": "non-technical, multiple events, limit"
    },
    {
        "question": "How many events can I participate in?",
        "answer": "You can participate in a maximum of 2 events:\n1. ONE Technical event\n2. ONE Non-Technical event\n\nThis means each register number can join exactly one event from the technical category and one event from the non-technical category, but not two events from the same category.",
        "intent": "registration_rules",
        "keywords": "how many, participate, events, maximum, limit"
    },
    {
        "question": "What happens if I try to register for the same event type twice?",
        "answer": "The system will not allow you to register for the same event type twice. If you attempt to register for a second technical event while already registered for another technical event, the registration will be rejected with an error message. Same applies for non-technical events.",
        "intent": "registration_rules",
        "keywords": "same event, twice, duplicate, error, rejected"
    },
    {
        "question": "Can I register for one technical and one non-technical event?",
        "answer": "Yes! That is exactly the intended usage. Each register number can register for:\n- ONE technical event (e.g., Coding Contest, Hackathon, Web Development)\n- ONE non-technical event (e.g., Quiz, Debate, Gaming)\n\nThis combination is allowed and encouraged.",
        "intent": "registration_rules",
        "keywords": "technical, non-technical, one each, allowed, combined"
    },
    {
        "question": "What are event categories at ARTIFA FEST?",
        "answer": "Events at ARTIFA FEST are categorized into two types:\n\n1. **Technical Events**: Programming, coding, development, and technology-focused competitions like Coding Contests, Hackathons, Web Development challenges, etc.\n\n2. **Non-Technical Events**: General knowledge, soft skills, and entertainment events like Quiz, Debate, Gaming, Creative competitions, etc.\n\nEach register number can participate in one event from each category.",
        "intent": "event_types",
        "keywords": "event types, categories, technical, non-technical, coding, programming"
    },
    {
        "question": "What is the registration limit rule?",
        "answer": "Registration Limit Rule: Each register number can register for a maximum of 2 events - ONE technical event and ONE non-technical event. This rule ensures fair participation and prevents any single participant from dominating multiple events of the same type.",
        "intent": "registration_rules",
        "keywords": "limit, rule, maximum, registration"
    },
    {
        "question": "I already registered for a technical event, can I register for another technical event?",
        "answer": "No, you cannot. Once a register number is registered for a technical event, the system will block any attempt to register for another technical event. You can only register for a non-technical event in addition to your existing technical event registration.",
        "intent": "registration_rules",
        "keywords": "already registered, second event, blocked, prevent"
    },
    {
        "question": "How do I check the registration rules?",
        "answer": "The registration rules at ARTIFA FEST are:\n\n✓ One register number = One technical event maximum\n✓ One register number = One non-technical event maximum\n✓ Total events per register number = Maximum 2\n✓ Cannot duplicate same event type\n✓ Can combine one technical + one non-technical\n\nYou can view the FAQ section in the chatbot by clicking 'Registration Rules' button to get more details.",
        "intent": "registration_rules",
        "keywords": "check rules, registration, view, FAQ"
    }
]

# Insert training data
created_count = 0
for data in training_data:
    try:
        # Check if similar question already exists
        existing = ChatbotTraining.objects.filter(
            question__iexact=data['question'],
            intent=data['intent']
        ).first()
        
        if not existing:
            training_obj = ChatbotTraining.objects.create(
                question=data['question'],
                answer=data['answer'],
                intent=data['intent'],
                keywords=data['keywords'],
                is_active=True
            )
            print(f"✓ Created: {data['question'][:50]}...")
            created_count += 1
        else:
            print(f"→ Skipped (already exists): {data['question'][:50]}...")
    except Exception as e:
        print(f"✗ Error creating training data: {data['question'][:50]}... - {str(e)}")

print(f"\n{'='*60}")
print(f"Total Training Data Inserted: {created_count}/{len(training_data)}")
print(f"{'='*60}")

# Display summary
total_training = ChatbotTraining.objects.filter(is_active=True).count()
print(f"\nTotal Active Training Entries: {total_training}")

# Show rule-related entries
rule_entries = ChatbotTraining.objects.filter(intent='registration_rules', is_active=True).count()
print(f"Registration Rule Entries: {rule_entries}")
