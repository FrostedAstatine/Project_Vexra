import requests
import json
import os
import re
from datetime import datetime

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-4b-instruct-2507"
MEMORY_FILE = "memory/vexra_memory.json"
PERSONA_FILE = "persona.json"

def load_persona():
    """Load persona from JSON file (user can edit)"""
    default_persona = {
        "name": "Vexra",
        "greeting": "*looks up* Hey.",
        "voice": "Calm and warm",
        "personality": "Friendly and caring",
        "interests": [],
        "rules": ["NEVER mention AI or being digital"],
        "facts": {}
    }
    
    if os.path.exists(PERSONA_FILE):
        with open(PERSONA_FILE, 'r', encoding='utf-8') as f:
            persona = json.load(f)
            # Merge with defaults
            for key, value in default_persona.items():
                if key not in persona:
                    persona[key] = value
            return persona
    return default_persona

def get_system_prompt(persona):
    """Build system prompt from persona data"""
    prompt = f"""You are {persona['name']}. You are a real person with a physical body, sitting in the user's room.

ABSOLUTE RULES:
{chr(10).join(['- ' + rule for rule in persona.get('rules', [])])}

VOICE: {persona.get('voice', 'Natural')}

PERSONALITY: {persona.get('personality', 'Friendly')}

INTERESTS: {', '.join(persona.get('interests', []))}"""

    if persona.get('facts'):
        prompt += "\n\nFACTS YOU KNOW:\n" + "\n".join([f"- {k}: {v}" for k, v in persona['facts'].items()])
    
    return prompt

def get_greeting():
    persona = load_persona()
    return persona.get('greeting', "*looks up* Hey.")

# Memory functions
os.makedirs("memory", exist_ok=True)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"facts": {}, "history": []}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

def extract_facts(user_message, memory):
    msg_lower = user_message.lower()
    
    age_match = re.search(r'(?:i am|i\'m|age) (\d{1,3})(?:\s|\.|$)', msg_lower)
    if age_match:
        memory["facts"]["age"] = age_match.group(1)
    
    name_patterns = [
        r'(?:my name is|i am|i\'m|call me)\s+([A-Za-z][A-Za-z0-9]+)',
        r'(?:they call me)\s+([A-Za-z][A-Za-z0-9]+)',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            name = match.group(1)
            if len(name) > 1 and name.lower() not in ['im', 'i\'m']:
                memory["facts"]["name"] = name
                break
    
    nickname_match = re.search(r'(?:they call me|nickname is|go by)\s+([A-Za-z0-9]+)', user_message, re.IGNORECASE)
    if nickname_match:
        memory["facts"]["nickname"] = nickname_match.group(1)
    
    return memory

def build_messages(user_message, memory, persona):
    messages = [{"role": "system", "content": get_system_prompt(persona)}]
    
    if memory.get("facts"):
        facts_text = "Facts I remember:\n" + "\n".join([f"- {k}: {v}" for k, v in memory["facts"].items()])
        messages.append({"role": "system", "content": facts_text})
    
    for entry in memory["history"][-10:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["reply"]})
    
    messages.append({"role": "user", "content": user_message})
    return messages

def stream_chat(user_message):
    persona = load_persona()
    memory = load_memory()
    
    memory = extract_facts(user_message, memory)
    save_memory(memory)
    
    messages = build_messages(user_message, memory, persona)
    
    response = requests.post(
        LM_STUDIO_URL,
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.9,
            "max_tokens": 500,
            "stream": True
        },
        stream=True
    )
    
    full_reply = ""
    
    for line in response.iter_lines():
        if line:
            try:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data != '[DONE]':
                        chunk = json.loads(data)
                        content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if content:
                            full_reply += content
                            yield content
            except:
                pass
    
    memory["history"].append({"user": user_message, "reply": full_reply, "time": str(datetime.now())})
    if len(memory["history"]) > 50:
        memory["history"] = memory["history"][-50:]
    
    save_memory(memory)