from django.db import models
from django.contrib.auth.models import User

class Event(models.Model):
    EVENT_TYPES = [
        ('technical', 'Technical'),
        ('non-technical', 'Non-Technical'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    is_team_event = models.BooleanField(default=False)
    min_team_size = models.IntegerField(default=1)
    max_team_size = models.IntegerField(default=1)
    icon_class = models.CharField(max_length=100, default='fas fa-code')
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    duration = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., '7 hours', '2 hours'")
    venue = models.CharField(max_length=200, blank=True, null=True, help_text="Event venue/location")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Registration(models.Model):
    YEAR_CHOICES = [
        ('1', '1st Year'),
        ('2', '2nd Year'),
        ('3', '3rd Year'),
        ('4', '4th Year'),
    ]
    
    DEPARTMENT_CHOICES = [
        ('AIDS', 'AI & DS'),
        ('CSE', 'Computer Science'),
        ('IT', 'Information Technology'),
        ('ECE', 'Electronics & Communication'),
        ('EEE', 'Electrical & Electronics'),
        ('MECH', 'Mechanical'),
        ('CIVIL', 'Civil'),
        ('OTHER', 'Other'),
    ]
    
    # Participant information (moved from Participant model)
    register_number = models.CharField(max_length=20, help_text='Registration number', null=True)
    full_name = models.CharField(max_length=200, null=True)
    year = models.CharField(max_length=1, choices=YEAR_CHOICES, null=True)
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES, null=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True)
    is_verified = models.BooleanField(default=False)
    
    # Event and registration details
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)
    
    # Team registration fields
    team = models.ForeignKey('Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='registrations', help_text='Team this registration belongs to')
    team_name = models.CharField(max_length=100, blank=True, null=True)
    team_members = models.IntegerField(default=0, help_text='Count of team members (0 if not team lead)')
    team_password = models.CharField(max_length=255, blank=True, null=True, help_text='Team password (hashed) for team login verification')
    is_team_lead = models.BooleanField(default=False, help_text='Whether this participant is a team lead')
    
    class Meta:
        unique_together = ['register_number', 'event']
        ordering = ['-registered_at']
        indexes = [
            models.Index(fields=['register_number']),
            models.Index(fields=['event', 'register_number']),
            models.Index(fields=['event', 'is_team_lead']),
            models.Index(fields=['-registered_at']),
        ]
    
    def __str__(self):
        return f"{self.full_name} ({self.register_number}) - {self.event}"

class Team(models.Model):
    """Model to store team information for group events"""
    name = models.CharField(max_length=200)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='teams')
    created_by = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='created_teams', help_text='The registration that created this team', null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True, help_text='Hashed password for team login')
    pending_members = models.TextField(blank=True, null=True, help_text='JSON list of pending member register numbers not yet registered')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['name', 'event']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', 'created_at']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.event.name}"
    
    @property
    def member_count(self):
        """Get count of joined team members"""
        return self.members.filter(status='joined').count()
    
    @property
    def pending_count(self):
        """Get count of pending team members"""
        return self.members.filter(status='pending').count()
    
    @property
    def total_count(self):
        """Get total count of all team members"""
        return self.members.count()

class TeamMember(models.Model):
    """Model to track team members with their status"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('joined', 'Joined'),
        ('declined', 'Declined'),
    ]
    
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='team_memberships', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    joined_at = models.DateTimeField(null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['team', 'registration']
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['team', 'status']),
            models.Index(fields=['registration', 'status']),
        ]
    
    def __str__(self):
        return f"{self.registration.full_name} - {self.team.name} ({self.status})"

class Schedule(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    date = models.DateField()
    is_break = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['date', 'start_time', 'order']
    
    def __str__(self):
        return f"{self.title} - {self.start_time} to {self.end_time}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} - {self.subject}"

class Coordinator(models.Model):
    EVENT_TYPES = [
        ('technical', 'Technical'),
        ('non-technical', 'Non-Technical'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='coordinators')
    name = models.CharField(max_length=200)
    register_number = models.CharField(max_length=20)
    year = models.CharField(max_length=1, choices=[('1', '1st Year'), ('2', '2nd Year'), ('3', '3rd Year'), ('4', '4th Year')])
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.event.name}"


class ErrorLog(models.Model):
    """Track all HTTP errors and exceptions"""
    ERROR_TYPES = [
        ('400', 'Bad Request'),
        ('401', 'Unauthorized'),
        ('403', 'Forbidden'),
        ('404', 'Not Found'),
        ('405', 'Method Not Allowed'),
        ('408', 'Request Timeout'),
        ('429', 'Too Many Requests'),
        ('500', 'Internal Server Error'),
        ('502', 'Bad Gateway'),
        ('503', 'Service Unavailable'),
        ('504', 'Gateway Timeout'),
        ('Exception', 'Exception'),
    ]
    
    status_code = models.IntegerField()
    error_type = models.CharField(max_length=50, choices=ERROR_TYPES)
    method = models.CharField(max_length=10)  # GET, POST, etc.
    path = models.CharField(max_length=500)
    query_string = models.TextField(blank=True, null=True)
    client_ip = models.CharField(max_length=50)
    user_agent = models.TextField(blank=True, null=True)
    error_message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['status_code']),
            models.Index(fields=['path']),
        ]
    
    def __str__(self):
        return f"{self.status_code} - {self.error_type} - {self.path} - {self.timestamp}"


class ChatbotTraining(models.Model):
    """Model to store chatbot training data (Q&A pairs)"""
    question = models.TextField(help_text="Training question that users might ask")
    answer = models.TextField(help_text="Chatbot response to this question")
    intent = models.CharField(max_length=100, blank=True, null=True, help_text="Intent category (e.g., registration_guide, team_guide)")
    keywords = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated keywords for this Q&A pair")
    is_active = models.BooleanField(default=True, help_text="Enable/disable this training pair")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chatbot_training_created')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['intent']),
            models.Index(fields=['is_active']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Q: {self.question[:50]}... → Intent: {self.intent}"
    
    @staticmethod
    def find_answer(user_question, confidence_threshold=0.2):
        """
        Search ChatbotTraining database for matching answer using optimized similarity.
        Optimized for short queries like acronyms (nec, aids, artifa).
        Returns (answer, confidence, training_pair) tuple or (None, 0, None)
        
        Args:
            user_question (str): Question from user
            confidence_threshold (float): Minimum confidence to return (0.0-1.0)
            
        Returns:
            tuple: (answer, confidence, training_pair) or (None, 0, None)
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            SKLEARN_AVAILABLE = True
        except ImportError:
            SKLEARN_AVAILABLE = False
        
        user_q_lower = user_question.lower().strip()
        user_words = set(user_q_lower.split())
        active_pairs = ChatbotTraining.objects.filter(is_active=True)
        
        best_match = None
        best_confidence = 0
        best_pair = None
        
        # Detect if this is a short query (1-2 words)
        is_short_query = len(user_words) <= 2
        
        for pair in active_pairs:
            # Check 1: Keyword matching (highest priority)
            keyword_match = 0
            if pair.keywords:
                keywords = [k.strip().lower() for k in pair.keywords.split(',')]
                # Check for exact or partial matches
                matched_keywords = sum(1 for kw in keywords if kw in user_q_lower or any(w in kw for w in user_words))
                if keywords:
                    keyword_match = matched_keywords / len(keywords)
            
            # Boost keyword matching for short queries
            if is_short_query and keyword_match > 0:
                keyword_match = min(1.0, keyword_match * 1.2)
            
            # Check 2: TF-IDF question similarity
            question_similarity = 0
            if SKLEARN_AVAILABLE:
                try:
                    vectorizer = TfidfVectorizer(lowercase=True, stop_words='english', min_df=1)
                    vectors = vectorizer.fit_transform([user_q_lower, pair.question.lower()])
                    question_similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
                except:
                    # Fallback to simple word overlap
                    pair_words = set(pair.question.lower().split())
                    if user_words and pair_words:
                        intersection = len(user_words & pair_words)
                        union = len(user_words | pair_words)
                        question_similarity = intersection / union if union > 0 else 0
            else:
                # Fallback to simple word overlap
                pair_words = set(pair.question.lower().split())
                if user_words and pair_words:
                    intersection = len(user_words & pair_words)
                    union = len(user_words | pair_words)
                    question_similarity = intersection / union if union > 0 else 0
            
            # Check 3: Intent-based matching
            intent_match = 0
            if pair.intent:
                for word in user_words:
                    if word in pair.intent.lower():
                        intent_match = 0.3
                        break
            
            # Boost intent for short queries
            if is_short_query and intent_match > 0:
                intent_match = 0.4
            
            # Combined confidence score (weighted)
            if is_short_query:
                confidence = (keyword_match * 0.6) + (question_similarity * 0.25) + (intent_match * 0.15)
            else:
                confidence = (keyword_match * 0.5) + (question_similarity * 0.35) + (intent_match * 0.15)
            
            if confidence > best_confidence and confidence >= confidence_threshold:
                best_confidence = confidence
                best_match = pair.answer
                best_pair = pair
        
        if best_match:
            return (best_match, round(best_confidence, 2), best_pair)
        
        return (None, 0, None)
    
    @staticmethod
    def get_suggestions(limit=10):
        """Get list of available training pairs for suggestions"""
        return ChatbotTraining.objects.filter(is_active=True)[:limit]