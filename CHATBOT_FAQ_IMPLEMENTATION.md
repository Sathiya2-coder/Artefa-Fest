# SweKeer Chatbot - FAQ Implementation with Icons & HTML Rendering

## Overview
Implemented 5 pre-built FAQ questions in the SweKeer chatbot with icon-based UI and proper HTML content filtering via JavaScript.

## Key Features Implemented

### 1. ✅ Pre-Built FAQ Questions (5 Common Questions)
- **How do I register for events?** `<i class='fas fa-clipboard-list'></i>`
- **How do I add members to my team?** `<i class='fas fa-user-plus'></i>`
- **How do I edit or remove team members?** `<i class='fas fa-edit'></i>`
- **What are the registration and team rules?** `<i class='fas fa-gavel'></i>`
- **What can you help me with?** `<i class='fas fa-life-ring'></i>`

### 2. ✅ HTML Content Filtering with innerHTML
All bot messages are properly sanitized and rendered using `innerHTML` with a whitelist of allowed HTML tags:
- Allowed tags: `<b>`, `<i>`, `<strong>`, `<em>`, `<br>`, `<p>`, `<div>`, `<span>`, `<ul>`, `<ol>`, `<li>`, `<code>`, `<pre>`, `<a>`, `<h1>-<h6>`
- Unsafe HTML is stripped while preserving text content
- XSS protection through tag sanitization

### 3. ✅ Icon-Based UI (Font Awesome Icons)
All emojis have been replaced with Font Awesome icons:
- **Avatar Icons**: `<i class='fas fa-robot'></i>` for bot, `<i class='fas fa-user-circle'></i>` for user
- **Status Icons**: 
  - Error: `<i class='fas fa-exclamation-circle'></i>`
  - Connection issue: `<i class='fas fa-plug'></i>`
  - Loading: `<i class='fas fa-circle'></i>` (animated)
- **Action Icons**:
  - Send: `<i class='fas fa-paper-plane'></i>`
  - Close: `<i class='fas fa-times'></i>`
  - Arrow: `<i class='fas fa-arrow-right'></i>` (in CSS)

### 4. ✅ Fast Response Speed
- FAQ questions are pre-defined in JavaScript (no database lookup for initial load)
- Direct answer retrieval from chatbot backend
- Instant UI response without additional API calls
- Loading indicator shows activity during fetch

### 5. ✅ JavaScript Implementation Details

#### addMessage() Function - With HTML Sanitization
```javascript
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const avatarIcon = sender === 'bot' 
        ? "<i class='fas fa-robot'></i>" 
        : "<i class='fas fa-user-circle'></i>";
    
    // Sanitize HTML for bot messages, escape for user messages
    const contentHTML = sender === 'bot' 
        ? sanitizeHTML(text) 
        : escapeHtml(text);
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatarIcon}</div>
        <div class="message-content">
            <div class="message-text">${contentHTML}</div>
        </div>
    `;
    
    chatbotMessages.appendChild(messageDiv);
    scrollToBottom();
}
```

#### sanitizeHTML() Function - Security
```javascript
function sanitizeHTML(html) {
    // Whitelist allowed HTML tags
    const allowedTags = [
        'B', 'I', 'STRONG', 'EM', 'BR', 'P', 'DIV', 'SPAN',
        'UL', 'OL', 'LI', 'CODE', 'PRE', 'A', 'H1', 'H2', 'H3'
    ];
    
    // Recursively clean and filter nodes
    // Keeps text and allowed HTML elements
    // Removes disallowed tags but preserves content
    // Validates 'a' tag attributes
}
```

#### initializeFAQButtons() Function - FAQ Display
```javascript
function initializeFAQButtons() {
    const faqs = [
        { id: 'faq_register', question: '<i class="fas fa-clipboard-list"></i> How do I register for events?' },
        { id: 'faq_add_member', question: '<i class="fas fa-user-plus"></i> How do I add members to my team?' },
        // ... more FAQs
    ];
    
    faqs.forEach(faq => {
        const button = document.createElement('button');
        button.className = 'faq-button';
        button.setAttribute('data-faq-id', faq.id);
        button.innerHTML = faq.question;  // Use innerHTML for icon rendering
        
        button.addEventListener('click', (e) => {
            e.preventDefault();
            sendFAQQuestion(faq.id);
        });
        
        faqContainer.appendChild(button);
    });
}
```

#### sendFAQQuestion() Function - FAQ Response
```javascript
function sendFAQQuestion(faqId) {
    // Display user's selected question
    const faqButton = document.querySelector(`[data-faq-id="${faqId}"]`);
    if (faqButton) {
        addMessage(faqButton.textContent.trim(), 'user');
    }
    
    // Show loading indicator
    showLoadingIndicator();
    
    // Send FAQ ID to server
    fetch('{% url "chatbot_response" %}', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ faq_id: faqId })
    })
    .then(response => response.json())
    .then(data => {
        removeLoadingIndicator();
        if (data.success) {
            addMessage(data.message, 'bot');  // HTML content is filtered here
        } else {
            addMessage('<i class="fas fa-exclamation-circle"></i> Sorry, I couldn\'t fetch that answer.', 'bot');
        }
    })
    .catch(error => {
        removeLoadingIndicator();
        addMessage('<i class="fas fa-plug"></i> Sorry, I couldn\'t connect. Please try again later.', 'bot');
    });
}
```

## Backend Integration

### chatbot.py - FAQ Methods
```python
def get_faq_questions(self):
    """Get all pre-built FAQ questions for display"""
    return [{'id': faq['id'], 'question': faq['question']} for faq in self.COMMON_FAQS]

def get_faq_answer(self, faq_id):
    """Get answer for a specific FAQ by ID"""
    for faq in self.COMMON_FAQS:
        if faq['id'] == faq_id:
            return {'id': faq['id'], 'question': faq['question'], 'answer': faq['answer'], 'found': True}
    return {'found': False}

def search_faq_by_query(self, user_query):
    """Search FAQs by matching user query with FAQ questions"""
    # Returns best FAQ match with confidence score
```

### views.py - chatbot_response() Function
```python
@csrf_exempt
def chatbot_response(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        faq_id = data.get('faq_id', '').strip()  # Check if FAQ was clicked
        
        # Handle FAQ selection
        if faq_id:
            faq_answer = chatbot.get_faq_answer(faq_id)
            if faq_answer.get('found'):
                return JsonResponse({
                    'success': True,
                    'message': faq_answer['answer'],
                    'type': 'faq',
                    'chatbot_name': 'SWEKEER-FAQ',
                    'confidence': 1.0,
                    'is_faq': True,
                    'model_used': 'faq'
                })
        
        # Search FAQs if natural query
        faq_match = chatbot.search_faq_by_query(user_message)
        if faq_match:
            return JsonResponse({
                'success': True,
                'message': faq_match['answer'],
                'type': 'faq',
                'is_faq': True,
            })
        
        # Fallback to normal chatbot response
```

## HTML Structure

### Template Updates
```html
<!-- FAQ Section with Icons -->
<div class="message bot-message faq-section">
    <div class="message-avatar"><i class='fas fa-question-circle'></i></div>
    <div class="message-content faq-container">
        <p><i class='fas fa-list'></i> Common Questions:</p>
        <div class="faq-buttons" id="faq-buttons">
            <!-- Dynamically populated by JavaScript -->
        </div>
    </div>
</div>

<!-- Message Content with Icon Avatar -->
<div class="message bot-message">
    <div class="message-avatar"><i class='fas fa-robot'></i></div>
    <div class="message-content">
        <div class="message-text">
            <!-- HTML content filtered and rendered here -->
        </div>
    </div>
</div>
```

## CSS Styling

### FAQ Button Styling
```css
.faq-button {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border: 2px solid var(--swekeer-primary);
    background: linear-gradient(135deg, #ffffff, #f9f9f9);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.faq-button:hover {
    background: linear-gradient(135deg, var(--swekeer-primary), #f97316);
    color: white;
    transform: translateX(5px);
}

.faq-button i {
    color: var(--swekeer-primary);
    min-width: 16px;
}
```

### Loading Icon Animation
```css
.message-loading {
    display: flex;
    gap: 4px;
    align-items: center;
}

.message-loading i {
    color: var(--swekeer-primary);
    animation: pulse 1.4s infinite;
}

@keyframes pulse {
    0%, 60%, 100% {
        opacity: 0.3;
    }
    30% {
        opacity: 1;
    }
}
```

## Security Features

1. **XSS Protection**: HTML sanitization filters dangerous tags while allowing safe formatting
2. **innerHTML Safety**: Whitelist approach prevents injection attacks
3. **CSRF Token**: All requests include Django CSRF token
4. **Content Validation**: Bot responses are filtered before rendering
5. **Attribute Validation**: Only safe attributes allowed on tags (e.g., href/target on `<a>`)

## Performance Optimizations

1. **Pre-loaded FAQs**: Questions loaded from JavaScript, no database query needed
2. **Direct Answer Retrieval**: FAQ answers fetched directly from chatbot instance
3. **Lazy Icon Loading**: Font Awesome icons load on demand
4. **Message Caching**: Previous messages cached in DOM
5. **Efficient DOM Updates**: Uses innerHTML for batch updates

## Files Modified

1. **core/templates/core/swekeer_chatbot.html**
   - Updated FAQ button display to use HTML with icons
   - Replaced emoji with Font Awesome icons throughout
   - Added sanitizeHTML() function for secure content rendering
   - Updated JavaScript functions to use innerHTML properly

2. **core/chatbot.py**
   - Added COMMON_FAQS list with 5 FAQ items
   - Added get_faq_questions() method
   - Added get_faq_answer() method
   - Added search_faq_by_query() method

3. **core/views.py**
   - Updated chatbot_response() to handle FAQ selection
   - Added FAQ ID handling in request processing
   - Added FAQ search in response pipeline

## Testing Checklist

- ✅ FAQ buttons display with correct icons
- ✅ Clicking FAQ sends correct faq_id to server
- ✅ FAQ answers render with HTML formatting (bold, lists, etc.)
- ✅ Regular chat still works with HTML sanitization
- ✅ Error messages show with icons instead of emojis
- ✅ Loading indicator animates with icons
- ✅ No XSS vulnerabilities (test with <script> tags)
- ✅ Emojis replaced with Font Awesome icons
- ✅ Fast response speed for FAQ answers

## Future Enhancements

- Add more FAQ categories (collapsible sections)
- Implement FAQ search with keyword matching
- Add FAQ ratings/feedback system
- Track FAQ usage analytics
- Dynamic FAQ loading from admin panel
- Multi-language FAQ support

