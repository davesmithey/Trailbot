"""
Pandora's Box of Rox Trail Race Chatbot Backend
Flask API for Pandora's Box of Rox race information chatbot
Powers the chat widget on tejastrails.com/pandoras
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests
from datetime import datetime
import logging
import re

app = Flask(__name__)
CORS(app)

# Setup logging
LOG_FILE = 'pandoras_chat.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # Also print to console (Render logs)
    ]
)
logger = logging.getLogger(__name__)

# Global state
conversations = {}  # Store per-user conversation history
knowledge_base = {}
knowledge_base_mtime = None
chat_log_entries = []  # Keep recent logs in memory for API access (max 500)

MAX_CONTEXT_CHARS = 16000
MAX_BLOCK_CHARS = 2500

def load_knowledge_base():
    """Load knowledge base from JSON file"""
    global knowledge_base, knowledge_base_mtime
    try:
        kb_file = 'pandoras_knowledge_base.json'
        with open(kb_file, 'r') as f:
            knowledge_base = json.load(f)
            knowledge_base_mtime = os.path.getmtime(kb_file)
            print(f"✓ Knowledge base loaded: {knowledge_base.get('race', {}).get('name', 'Unknown')}")
    except FileNotFoundError:
        print("⚠ pandoras_knowledge_base.json not found")
        knowledge_base = {}
        knowledge_base_mtime = None
    except json.JSONDecodeError:
        print("⚠ Invalid JSON in pandoras_knowledge_base.json")
        knowledge_base = {}
        knowledge_base_mtime = None

def reload_knowledge_base_if_changed():
    """Reload JSON when the scheduler updates it in the same runtime."""
    global knowledge_base_mtime
    kb_file = 'pandoras_knowledge_base.json'
    try:
        current_mtime = os.path.getmtime(kb_file)
    except FileNotFoundError:
        return

    if knowledge_base_mtime is None or current_mtime != knowledge_base_mtime:
        load_knowledge_base()

def normalize_text(text):
    """Normalize text for lightweight keyword matching."""
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()

def get_keywords(text):
    """Extract useful search words from a user question."""
    stop_words = {
        'a', 'an', 'and', 'are', 'at', 'be', 'can', 'do', 'does', 'for', 'from',
        'how', 'i', 'in', 'is', 'it', 'me', 'my', 'of', 'on', 'or', 'the',
        'there', 'to', 'what', 'when', 'where', 'who', 'with', 'you'
    }
    return [word for word in normalize_text(text).split() if len(word) > 2 and word not in stop_words]

def score_text(text, keywords):
    """Score a knowledge-base block by keyword hits."""
    normalized = normalize_text(text)
    if not keywords:
        return (0, 0, 0, 0)

    matched_keywords = sum(1 for keyword in keywords if keyword in normalized)
    exact_phrase = 1 if normalize_text(' '.join(keywords)) in normalized else 0
    all_keywords = 1 if matched_keywords == len(keywords) else 0
    hit_count = sum(normalized.count(keyword) for keyword in keywords)
    return (all_keywords, exact_phrase, matched_keywords, hit_count)

def trim_block(block):
    """Keep retrieved sections compact enough to fit several useful matches."""
    if len(block) <= MAX_BLOCK_CHARS:
        return block
    return block[:MAX_BLOCK_CHARS].rsplit('\n', 1)[0] + "\n[...]"

def relevant_knowledge(user_message):
    """Return a compact slice of the KB instead of sending the whole JSON."""
    keywords = get_keywords(user_message)
    race = knowledge_base.get('race', {})
    quick_reference = {
        'race': race,
        'distances': knowledge_base.get('distances', []),
        'race_type': knowledge_base.get('race_type'),
        'schedule': knowledge_base.get('schedule', {}),
        'course': knowledge_base.get('course', {}),
        'overview': knowledge_base.get('overview', {}),
        'registration': knowledge_base.get('registration', {}),
        'venue_details': knowledge_base.get('venue_details', {}),
        'race_info': knowledge_base.get('race_info', {}),
        'waiver': knowledge_base.get('waiver', {}),
    }

    candidates = []
    for page_name, page_data in knowledge_base.get('source_pages', {}).items():
        for heading, content in page_data.get('sections', {}).items():
            block = f"{page_name.upper()} - {heading}\n{content}"
            candidates.append((score_text(block, keywords), trim_block(block)))

    for heading, content in knowledge_base.get('policies', {}).get('sections', {}).items():
        block = f"POLICIES - {heading}\n{content}"
        candidates.append((score_text(block, keywords), trim_block(block)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = [block for score, block in candidates if score[2] > 0][:8]

    if not selected:
        for page_name, page_data in knowledge_base.get('source_pages', {}).items():
            overview = page_data.get('sections', {}).get('Overview')
            if overview:
                selected.append(f"{page_name.upper()} - Overview\n{overview}")

    context = json.dumps(quick_reference, indent=2)
    for block in selected:
        if len(context) + len(block) + 3 > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - len(context) - 3
            if remaining > 500:
                context += "\n\n" + block[:remaining]
            break
        context += "\n\n" + block

    return context

def get_system_prompt(user_message=''):
    """Build system prompt with knowledge base context"""
    reload_knowledge_base_if_changed()
    race_name = knowledge_base.get('race', {}).get('name', 'Pandora\'s Box of Rox')
    distances = ", ".join(knowledge_base.get('distances', []))
    venue = knowledge_base.get('race', {}).get('location', {}).get('venue', 'Unknown')
    city = knowledge_base.get('race', {}).get('location', {}).get('city', 'Unknown')
    date = knowledge_base.get('schedule', {}).get('raceWeekend', {}).get('date', 'April 25, 2026')

    knowledge_context = f"""
QUICK REFERENCE - {race_name}:
- Race Name: {race_name}
- Date: {date}
- Location: {venue}, {city}
- Available Distances: {distances}
- Terrain: {knowledge_base.get('course', {}).get('terrain', 'Trail running')}
- Spectators: Free admission
- Family Friendly: Yes
- Beginner Friendly: Yes (8 mile and 4 mile options available)

RELEVANT KNOWLEDGE BASE EXCERPTS:
{relevant_knowledge(user_message)}

INSTRUCTIONS:
1. You are a helpful, friendly chatbot for the {race_name} trail race
2. Search the knowledge base above to answer questions
3. Be enthusiastic about the race and trail running
4. If user asks about policies, use the relevant policies excerpts above
5. If info is in the knowledge base, use it. If not available, say "I don't have that information yet"
6. Keep responses concise but informative
7. Encourage people to register or volunteer
8. Be supportive and motivating about trail running

MANDATORY:
- Always be friendly and encouraging
- Keep responses under 150 words
- Focus on race-specific details when asked
- Mention unique features: free spectators, unique swag, unrivaled course markings, post-race celebration
- Suggest volunteering or registering when appropriate
"""

    return f"""You are a helpful trail running chatbot for {race_name}.

{knowledge_context}

Answer questions about {race_name} using the knowledge base provided. Be friendly, encouraging, and informative."""

def call_claude_api(system_prompt, messages):
    """Call Claude API directly via requests (bypasses SDK issues)"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }

    payload = {
        'model': 'claude-sonnet-4-6',
        'max_tokens': 500,
        'system': system_prompt,
        'messages': messages
    }

    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers=headers,
        json=payload,
        timeout=30
    )

    if not response.ok:
        logger.error(f"Anthropic API error {response.status_code}: {response.text[:1000]}")
        response.raise_for_status()
    return response.json()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    reload_knowledge_base_if_changed()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'race': knowledge_base.get('race', {}).get('name', 'Unknown')
    })

@app.route('/api/knowledge-base', methods=['GET'])
def get_knowledge_base():
    """Get current knowledge base"""
    reload_knowledge_base_if_changed()
    return jsonify(knowledge_base)

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint - main interaction point"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id') or data.get('session_id') or 'anonymous'
        race_id = data.get('raceId', 'pandoras-box-of-rox')
        timestamp = datetime.now().isoformat()

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Initialize conversation history if needed
        if user_id not in conversations:
            conversations[user_id] = []

        # Keep last 4 exchanges (8 messages). The KB excerpts carry the facts.
        conversation = conversations[user_id][-8:] if len(conversations[user_id]) > 8 else conversations[user_id]

        # Add user message to history
        conversation.append({
            'role': 'user',
            'content': user_message
        })

        # Call Claude API with conversation history
        api_response = call_claude_api(get_system_prompt(user_message), conversation)

        # Extract response
        assistant_message = api_response['content'][0]['text']

        # Add assistant response to history
        conversation.append({
            'role': 'assistant',
            'content': assistant_message
        })

        # Update conversations
        conversations[user_id] = conversation

        # Log the interaction
        log_entry = {
            'timestamp': timestamp,
            'user_id': user_id,
            'user_message': user_message,
            'assistant_response': assistant_message,
            'race_id': race_id
        }
        chat_log_entries.append(log_entry)
        if len(chat_log_entries) > 500:  # Keep max 500 in memory
            chat_log_entries.pop(0)

        logger.info(f"[{user_id}] User: {user_message[:100]}")
        logger.info(f"[{user_id}] Bot: {assistant_message[:100]}")

        return jsonify({
            'response': assistant_message,
            'user_id': user_id,
            'timestamp': timestamp
        })

    except Exception as e:
        logger.error(f"Chat error: {type(e).__name__}: {str(e)}")
        return jsonify({
            'error': 'An error occurred processing your message',
            'details': str(e)
        }), 500

@app.route('/stats', methods=['GET'])
def stats():
    """Get usage statistics"""
    total_messages = sum(len(conv) for conv in conversations.values())
    return jsonify({
        'active_conversations': len(conversations),
        'total_messages': total_messages,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/clear-history', methods=['POST'])
def clear_history():
    """Clear conversation history for a user"""
    try:
        user_id = request.json.get('user_id')
        if user_id in conversations:
            del conversations[user_id]
            return jsonify({'status': 'cleared', 'user_id': user_id})
        return jsonify({'status': 'not_found', 'user_id': user_id}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent chat logs"""
    limit = request.args.get('limit', 100, type=int)
    recent_logs = chat_log_entries[-limit:] if limit > 0 else chat_log_entries
    return jsonify({
        'total_entries': len(chat_log_entries),
        'returned': len(recent_logs),
        'logs': recent_logs
    })

@app.route('/logs/download', methods=['GET'])
def download_logs():
    """Download raw log file"""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                log_content = f.read()
            return log_content, 200, {'Content-Type': 'text/plain', 'Content-Disposition': 'attachment; filename=pandoras_chat.log'}
        return jsonify({'error': 'Log file not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

load_knowledge_base()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
