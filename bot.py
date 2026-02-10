"""
Messenger Bot - Groq API powered with per-user memory
"""
from flask import Flask, request, jsonify
import requests
import os
import time
import logging
from typing import Dict, List, Optional
from config import (
    PAGE_ACCESS_TOKEN,
    VERIFY_TOKEN,
    GROQ_API_KEY,
    GROQ_API_URL,
    GROQ_MODEL_HIERARCHY,
    GROQ_SYSTEM_PROMPT,
    GROQ_TEMPERATURE,
    GROQ_MAX_TOKENS,
    MEMORY_MAX_MESSAGES,
    MEMORY_IDLE_TIMEOUT
)

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONVERSATION MEMORY
# =============================================================================

# Per-user conversation history: {user_id: {"messages": [...], "last_active": timestamp}}
conversation_memory: Dict[str, dict] = {}
processed_messages = set()  # Deduplication cache
MESSAGE_CACHE_SIZE = 200

def get_user_memory(user_id: str) -> List[dict]:
    """Get conversation history for a user, clearing if idle too long."""
    current_time = time.time()
    
    if user_id in conversation_memory:
        user_data = conversation_memory[user_id]
        # Check if memory has expired
        if current_time - user_data["last_active"] > MEMORY_IDLE_TIMEOUT:
            logger.info(f"Memory expired for user {user_id}, clearing...")
            conversation_memory[user_id] = {"messages": [], "last_active": current_time}
            return []
        return user_data["messages"]
    else:
        # Initialize memory for new user
        conversation_memory[user_id] = {"messages": [], "last_active": current_time}
        return []

def add_to_memory(user_id: str, role: str, content: str):
    """Add a message to user memory."""
    if user_id not in conversation_memory:
        conversation_memory[user_id] = {"messages": [], "last_active": time.time()}
    
    user_data = conversation_memory[user_id]
    user_data["last_active"] = time.time()
    user_data["messages"].append({"role": role, "content": content})
    
    # Trim to max messages
    if len(user_data["messages"]) > MEMORY_MAX_MESSAGES:
        user_data["messages"] = user_data["messages"][-MEMORY_MAX_MESSAGES:]

# =============================================================================
# GROQ API HANDLER
# =============================================================================

def generate_response(user_id: str, prompt: str) -> str:
    """Generate response using Groq API with conversation memory and fallback."""
    # Get existing conversation history
    history = get_user_memory(user_id)
    
    # Add current user message to memory
    add_to_memory(user_id, "user", prompt)
    
    # Build messages list: system + history + current
    messages = [{"role": "system", "content": GROQ_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    
    # Try each model in the hierarchy
    for model in GROQ_MODEL_HIERARCHY:
        try:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": GROQ_TEMPERATURE,
                    "max_tokens": GROQ_MAX_TOKENS,
                },
                timeout=30
            )
            
            if response.status_code == 429:
                logger.warning(f"Rate limited on {model}, trying next model...")
                continue
                
            response.raise_for_status()
            
            # Success
            result = response.json()["choices"][0]["message"]["content"].strip()
            
            # Add assistant response to memory
            add_to_memory(user_id, "assistant", result)
            
            logger.info(f"Response generated for {user_id} using {model}")
            return result
            
        except requests.RequestException as e:
            logger.warning(f"Error with {model}: {e}, trying next model...")
            continue
            
    return "Sorry, I'm having trouble thinking right now. Please try again later."

# =============================================================================
# FACEBOOK WEBHOOK HANDLERS
# =============================================================================

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token == VERIFY_TOKEN:
        return challenge
    return 'Verification failed', 403

@app.route('/webhook', methods=['POST'])
def handle_messages():
    data = request.json
    
    if data.get('object') != 'page':
        return jsonify({'status': 'not a page event'}), 404
    
    for entry in data.get('entry', []):
        for event in entry.get('messaging', []):
            if 'delivery' in event or 'read' in event:
                continue
                
            if 'message' in event and 'text' in event['message']:
                # Deduplication logic
                message_id = event['message'].get('mid')
                if message_id in processed_messages:
                    continue
                processed_messages.add(message_id)
                if len(processed_messages) > MESSAGE_CACHE_SIZE:
                    processed_messages.pop()

                sender_id = event['sender']['id']
                message_text = event['message']['text']
                
                # Check for reply context (if available) - FB provides reply_to mid but not content directly
                # For basic implementation, we just use conversation memory which serves similar purpose
                
                logger.info(f"Processing message from {sender_id}: {message_text}")
                
                # Show typing indicator
                send_action(sender_id, "typing_on")
                
                # Generate and send response
                response_text = generate_response(sender_id, message_text)
                send_message(sender_id, response_text)
                
                send_action(sender_id, "typing_off")
    
    return jsonify({'status': 'success'}), 200

def send_message(recipient_id, text):
    """Send text message to user."""
    url = f'https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}'
    
    # Split long messages
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    
    for chunk in chunks:
        requests.post(url, json={
            'recipient': {'id': recipient_id},
            'message': {'text': chunk}
        })

def send_action(recipient_id, action):
    """Send sender action (typing_on, mark_seen, etc)."""
    url = f'https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}'
    requests.post(url, json={
        'recipient': {'id': recipient_id},
        'sender_action': action
    })

if __name__ == '__main__':
    app.run(port=5000, debug=True)