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

app = Flask(__name__)
CORS(app)

# Global state
conversations = {}  # Store per-user conversation history
knowledge_base = {}

def load_knowledge_base():
    """Load knowledge base from JSON file"""
    global knowledge_base
    try:
        with open('pandoras_knowledge_base.json', 'r') as f:
            knowledge_base = json.load(f)
            print(f"✓ Knowledge base loaded: {knowledge_base.get('race', {}).get('name', 'Unknown')}")
    except FileNotFoundError:
        print("⚠ pandoras_knowledge_base.json not found")
        knowledge_base = {}
    except json.JSONDecodeError:
        print("⚠ Invalid JSON in pandoras_knowledge_base.json")
        knowledge_base = {}

def get_system_prompt():
    """Build system prompt with knowledge base context"""
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

FULL KNOWLEDGE BASE:
{json.dumps(knowledge_base, indent=2)}

INSTRUCTIONS:
1. You are a helpful, friendly chatbot for the {race_name} trail race
2. Search the knowledge base above to answer questions
3. Be enthusiastic about the race and trail running
4. If info is in the knowledge base, use it. If not available, say "I don't have that information yet"
5. Keep responses concise but informative
6. Encourage people to register or volunteer
7. Be supportive and motivating about trail running

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
        json=payload
    )

    response.raise_for_status()
    return response.json()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'race': knowledge_base.get('race', {}).get('name', 'Unknown')
    })

@app.route('/api/knowledge-base', methods=['GET'])
def get_knowledge_base():
    """Get current knowledge base"""
    return jsonify(knowledge_base)

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint - main interaction point"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id', 'anonymous')
        race_id = data.get('raceId', 'pandoras-box-of-rox')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Initialize conversation history if needed
        if user_id not in conversations:
            conversations[user_id] = []

        # Keep last 10 exchanges (20 messages)
        conversation = conversations[user_id][-20:] if len(conversations[user_id]) > 20 else conversations[user_id]

        # Add user message to history
        conversation.append({
            'role': 'user',
            'content': user_message
        })

        # Call Claude API with conversation history
        api_response = call_claude_api(get_system_prompt(), conversation)

        # Extract response
        assistant_message = api_response['content'][0]['text']

        # Add assistant response to history
        conversation.append({
            'role': 'assistant',
            'content': assistant_message
        })

        # Update conversations
        conversations[user_id] = conversation

        return jsonify({
            'response': assistant_message,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"Chat error: {type(e).__name__}: {str(e)}")
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

if __name__ == '__main__':
    load_knowledge_base()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
