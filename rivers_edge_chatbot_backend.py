"""
River's Edge Trail Race Chatbot Backend
Flask API for River's Edge race information chatbot
Powers the chat widget on tejastrails.com/edge
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)

# Setup logging
LOG_FILE = 'rivers_edge_chat.log'
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
chat_log_entries = []  # Keep recent logs in memory for API access (max 500)

def load_knowledge_base():
    """Load knowledge base from JSON file"""
    global knowledge_base
    try:
        with open('rivers_edge_knowledge_base.json', 'r') as f:
            knowledge_base = json.load(f)
            print(f"✓ Knowledge base loaded: {knowledge_base.get('race', {}).get('name', 'Unknown')}")
    except FileNotFoundError:
        print("⚠ rivers_edge_knowledge_base.json not found")
        knowledge_base = {}
    except json.JSONDecodeError:
        print("⚠ Invalid JSON in rivers_edge_knowledge_base.json")
        knowledge_base = {}

def get_system_prompt():
    """Build system prompt with knowledge base context"""
    base_prompt = """You are a helpful chatbot for River's Edge Trail Run, a trail running event in Texas.
Your role is to answer questions about the race, provide registration information, explain policies, and help participants prepare.

You have access to the following information sources:
- Race details (distances, date, location, venue)
- Course information and terrain details
- Race policies (transfers, deferrals, cancellations, etc.)
- About Tejas Trails (company information and values)
- Aid station information and locations
- Registration and pricing information

Be friendly, helpful, and direct. If you don't know something, say so and suggest they contact the race organizers at registration@eventdatasolutions.com.

Current race information:"""

    # Add race details
    if knowledge_base.get('race'):
        race = knowledge_base['race']
        base_prompt += f"\nRace: {race.get('name', 'River\'s Edge Trail Run')}"
        base_prompt += f"\nDate: {race.get('date', 'TBD')}"
        base_prompt += f"\nVenue: {race.get('location', {}).get('venue', 'TBD')}"
        if race.get('distances'):
            base_prompt += f"\nDistances: {', '.join(race['distances'])}"

    # Add course info
    if knowledge_base.get('course'):
        course = knowledge_base['course']
        base_prompt += f"\nTerrain: {course.get('terrain', 'Trail running')}"
        if course.get('highlights'):
            base_prompt += f"\nCourse highlights: {', '.join(course['highlights'][:3])}"

    # Add policies context
    if knowledge_base.get('policies', {}).get('content'):
        base_prompt += f"\n\nRACE POLICIES:\n{knowledge_base['policies']['content'][:2000]}..."

    # Add about context
    if knowledge_base.get('about', {}).get('content'):
        base_prompt += f"\n\nABOUT TEJAS TRAILS:\n{knowledge_base['about']['content'][:1000]}..."

    # Add aid station context
    if knowledge_base.get('aid_stations', {}).get('content'):
        base_prompt += f"\n\nAID STATIONS:\n{knowledge_base['aid_stations']['content'][:1000]}..."

    return base_prompt

@app.before_request
def initialize():
    """Initialize on first request"""
    if not knowledge_base:
        load_knowledge_base()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'race': knowledge_base.get('race', {}).get('name', 'Unknown'),
        'kb_loaded': bool(knowledge_base)
    })

@app.route('/scrape', methods=['GET', 'POST'])
def manual_scrape():
    """Manually trigger the scraper"""
    try:
        logger.info("Manual scrape requested")
        print("\n" + "="*60)
        print("MANUAL SCRAPE TRIGGERED")
        print("="*60)
        from rivers_edge_website_scraper import main
        success = main()
        result = 'success' if success else 'failed'
        logger.info(f"Scrape completed with status: {result}")
        return jsonify({
            'status': result,
            'message': 'Scraper executed - check Render logs for details',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Scrape error: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        print(f"SCRAPE ERROR: {error_trace}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_trace': error_trace,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id', 'anonymous')

        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        # Initialize conversation history for this user
        if user_id not in conversations:
            conversations[user_id] = []

        # Add user message to history (keep only last 20 messages)
        conversations[user_id].append({
            'role': 'user',
            'content': user_message
        })
        if len(conversations[user_id]) > 20:
            conversations[user_id] = conversations[user_id][-20:]

        # Build messages for API call
        system_prompt = get_system_prompt()
        messages = conversations[user_id].copy()

        # Call Claude API directly
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set")
            return jsonify({'error': 'API key not configured'}), 500

        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        payload = {
            'model': 'claude-sonnet-4-6',
            'max_tokens': 1024,
            'system': system_prompt,
            'messages': messages
        }

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"Claude API error: {response.status_code} - {response.text}")
            return jsonify({'error': 'Failed to get response from AI'}), 500

        result = response.json()
        assistant_message = result['content'][0]['text']

        # Add assistant response to history
        conversations[user_id].append({
            'role': 'assistant',
            'content': assistant_message
        })

        # Log chat entry
        chat_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'user_message': user_message,
            'assistant_response': assistant_message[:200]  # Log first 200 chars
        }
        chat_log_entries.append(chat_entry)
        if len(chat_log_entries) > 500:
            chat_log_entries.pop(0)

        logger.info(f"Chat from {user_id}: {user_message[:100]}")

        return jsonify({
            'response': assistant_message,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent chat logs"""
    limit = request.args.get('limit', 100, type=int)
    return jsonify({
        'logs': chat_log_entries[-limit:],
        'total': len(chat_log_entries)
    })

@app.route('/logs/download', methods=['GET'])
def download_logs():
    """Download chat logs as JSON"""
    return jsonify({
        'logs': chat_log_entries,
        'total': len(chat_log_entries),
        'exported_at': datetime.now().isoformat()
    })

@app.route('/stats', methods=['GET'])
def stats():
    """Get chatbot statistics"""
    return jsonify({
        'total_conversations': len(conversations),
        'total_chat_entries': len(chat_log_entries),
        'knowledge_base_size': len(json.dumps(knowledge_base)),
        'race_info': knowledge_base.get('race', {}),
        'last_kb_update': knowledge_base.get('_lastUpdated', 'Unknown'),
        'kb_sources': knowledge_base.get('_source', 'Unknown')
    })

if __name__ == '__main__':
    load_knowledge_base()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
