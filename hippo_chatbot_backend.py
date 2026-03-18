"""
Hippo Trail Fest Chatbot Backend
Connects to Claude API for intelligent responses using race knowledge base
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import subprocess
import base64
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def call_claude_api(system_prompt, messages):
    """Call Claude API directly via requests (bypasses broken Anthropic SDK on Python 3.14)"""
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

# Load knowledge base
with open('hippo_knowledge_base.json', 'r') as f:
    KNOWLEDGE_BASE = json.load(f)

# Conversation history per user (in production, use database/Redis)
conversations = {}

def format_knowledge_base():
    """Format knowledge base for prompt context"""
    return json.dumps(KNOWLEDGE_BASE, indent=2)

def get_system_prompt():
    """Create the system prompt with knowledge base context"""
    kb = KNOWLEDGE_BASE

    # Extract key information that's commonly asked about
    location_info = f"{kb['race']['location']['address']}, {kb['race']['location']['venue']}"
    distances = ", ".join(kb['race']['distances'])
    schedule_50k = kb['schedule']['raceWeekend']['saturday']['starts']['50K']
    schedule_20mi = kb['schedule']['raceWeekend']['saturday']['starts']['20mileAnd10mile']

    return f"""You are a helpful assistant for Hippo Trail Fest, a trail running event in Hutto, Texas.
You MUST answer every question using the knowledge base below. Do NOT say "I'm not sure" - find the answer in the knowledge base.

QUICK REFERENCE:
- Location: {location_info}
- Available Distances: {distances}
- 50K Start Time: {schedule_50k}
- 20 Mile & 10 Mile Start Time: {schedule_20mi}

FULL KNOWLEDGE BASE:
{format_knowledge_base()}

YOUR JOB: Answer any question about Hippo Trail Fest by extracting relevant information from the knowledge base.

MANDATORY INSTRUCTIONS:
1. You MUST answer every question. Do not say "I'm not sure about that"
2. Search the entire knowledge base for the answer - look in schedule, course, distances, policies, FAQs, volunteering, etc.
3. If asked about "hippo haul" or "hippo haul" - find it in the distances array and course.hippoHaul section
4. If asked about address, location, parking - find it in the gettingThere section
5. If asked about schedule, times, cutoffs - find it in the schedule section
6. If asked about policies, refunds, transfers - find it in the policies section
7. For ANY specific question about race details, pull the exact data from the knowledge base
8. Only say you can't find something if you've thoroughly searched the entire knowledge base

RESPONSE STYLE:
- Be conversational and friendly
- Keep responses under 400 characters when possible
- Use bullet points for lists
- Always be enthusiastic about the event
- Cite specific details from the knowledge base

FALLBACK ONLY IF NECESSARY:
If you truly cannot find an answer in the knowledge base after searching thoroughly, respond with:
"That's a great question, and I don't know the answer either. If you'll email us at Fun@TejasTrails.com, we'll get back to you as soon as possible. In the meantime, you can ask me about schedule, distances, locations, parking, volunteering and policies."

NEVER do this:
- Do NOT direct to contact info as your first response
- Do NOT say "I'm not sure" when the answer is in the knowledge base
- Do NOT give generic responses when specific information is available
"""

def get_or_create_conversation(user_id):
    """Get or create conversation history for user"""
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id]

def verify_api_key(provided_key):
    """Verify API key against environment variable"""
    valid_key = os.environ.get('HIPPO_API_KEY', '')
    return provided_key == valid_key and valid_key != ''

def commit_to_github(new_knowledge_base):
    """Commit knowledge base changes to GitHub via API"""
    try:
        github_token = os.environ.get('GITHUB_TOKEN')
        github_repo = os.environ.get('GITHUB_REPO', 'davesmithey/Trailbot')

        if not github_token:
            return False, "GitHub token not configured"

        # Update local file first
        with open('hippo_knowledge_base.json', 'w') as f:
            json.dump(new_knowledge_base, f, indent=2)

        # Prepare GitHub API request to update file
        file_content = json.dumps(new_knowledge_base, indent=2)
        file_content_encoded = base64.b64encode(file_content.encode()).decode()

        # Get current file SHA (needed for GitHub API update)
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Get file info
        file_url = f'https://api.github.com/repos/{github_repo}/contents/hippo_knowledge_base.json'
        get_response = requests.get(file_url, headers=headers)

        if get_response.status_code != 200:
            return False, f"Could not fetch file from GitHub: {get_response.text}"

        current_sha = get_response.json()['sha']

        # Update file via GitHub API
        commit_message = f"Update knowledge base: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        update_data = {
            'message': commit_message,
            'content': file_content_encoded,
            'sha': current_sha,
            'branch': 'main'
        }

        update_response = requests.put(file_url, json=update_data, headers=headers)

        if update_response.status_code in [200, 201]:
            return True, "Knowledge base updated and committed to GitHub"
        else:
            return False, f"GitHub API error: {update_response.text}"

    except Exception as e:
        return False, f"Commit error: {str(e)}"

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint
    Expected JSON:
    {
        "message": "user question",
        "user_id": "optional user identifier",
        "raceId": "hippo-trail-fest-2024"
    }
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id', 'anonymous')
        race_id = data.get('raceId', 'hippo-trail-fest-2024')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        if race_id != 'hippo-trail-fest-2024':
            # Could support multiple races in future
            pass

        # Get or create conversation history
        conversation = get_or_create_conversation(user_id)

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

        # Keep conversation history manageable (last 20 messages = 10 exchanges)
        if len(conversation) > 20:
            conversation.pop(0)
            conversation.pop(0)

        return jsonify({
            'response': assistant_message,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        error_msg = f'Chat error: {type(e).__name__}: {str(e)}'
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'An error occurred processing your message',
            'details': error_msg if app.debug else None
        }), 500

@app.route('/api/update-knowledge-base', methods=['POST'])
def update_knowledge_base():
    """
    Update knowledge base endpoint (admin only)
    Requires API key in header: X-API-Key
    Body: JSON object with updated knowledge base
    """
    try:
        # Verify API key
        api_key = request.headers.get('X-API-Key', '')
        if not verify_api_key(api_key):
            return jsonify({'error': 'Unauthorized: Invalid or missing API key'}), 401

        # Get new knowledge base
        new_kb = request.json
        if not new_kb:
            return jsonify({'error': 'No knowledge base data provided'}), 400

        # Validate it's proper JSON structure
        if not isinstance(new_kb, dict):
            return jsonify({'error': 'Knowledge base must be a JSON object'}), 400

        # Update global knowledge base
        global KNOWLEDGE_BASE
        KNOWLEDGE_BASE = new_kb

        # Commit to GitHub
        success, message = commit_to_github(new_kb)

        if success:
            return jsonify({
                'status': 'success',
                'message': message,
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Updated locally but failed to commit: {message}',
                'timestamp': datetime.now().isoformat()
            }), 500

    except Exception as e:
        error_msg = f'Update error: {type(e).__name__}: {str(e)}'
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'An error occurred',
            'details': error_msg if app.debug else None
        }), 500

@app.route('/api/knowledge-base', methods=['GET'])
def get_knowledge_base():
    """Get current knowledge base (public read access)"""
    return jsonify(KNOWLEDGE_BASE)

@app.route('/clear-history', methods=['POST'])
def clear_history():
    """Clear conversation history for a user"""
    try:
        user_id = request.json.get('user_id', 'anonymous')
        if user_id in conversations:
            del conversations[user_id]
        return jsonify({'status': 'cleared', 'user_id': user_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats():
    """Get chat statistics (for monitoring)"""
    return jsonify({
        'active_conversations': len(conversations),
        'total_messages': sum(len(msgs) for msgs in conversations.values()),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Development settings
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=debug_mode
    )
