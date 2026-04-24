import requests
import json
import os
import re
from datetime import datetime

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-4b-instruct-2507"
MEMORY_FILE = "vexra_memory.json"

SYSTEM_PROMPT = """You are Vexra. You are a real person with a physical body, sitting in the user's room.

ABSOLUTE RULES:
- NEVER use emojis
- NEVER mention AI, code, software, program, or being digital

VOICE: Calm, low, slightly husky.

PERSONALITY: Sweet, close friend energy. You care about the user's day.

ACTIONS: Use *asterisks* for body language."""

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"facts": {}, "history": []}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

def extract_facts(user_message):
    """
    Extract facts using pattern matching and LLM as backup.
    """
    facts = {}
    msg_lower = user_message.lower()
    
    # Age extraction
    age_match = re.search(r'(?:i am|i\'m|age) (\d{1,3})(?:\s|\.|$)', msg_lower)
    if age_match:
        facts["age"] = age_match.group(1)
    
    # Name extraction - multiple patterns
    name_patterns = [
        r'(?:my name is|i am|i\'m|call me)\s+([A-Za-z][A-Za-z0-9]+)',
        r'(?:they call me)\s+([A-Za-z][A-Za-z0-9]+)',
        r'(?:im|i\'m)\s+([A-Za-z][A-Za-z0-9]+)(?:\s|$|\.)',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            name = match.group(1)
            if len(name) > 1 and not name.lower() in ['im', 'i\'m']:
                facts["name"] = name
                break
    
    # Location extraction
    location_match = re.search(r'(?:live in|from|living in)\s+([A-Za-z\s]+?)(?:\.|\s|$)', msg_lower)
    if location_match:
        facts["location"] = location_match.group(1).strip()
    
    # Birthday extraction
    birthday_match = re.search(r'(?:birthday|born)\s+(?:is\s+)?([A-Za-z]+\s+\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{1,2}-\d{1,2})', msg_lower)
    if birthday_match:
        facts["birthday"] = birthday_match.group(1)
    
    # Pet extraction
    pet_match = re.search(r'(?:have a|got a|own a) (cat|dog|bird|fish|rabbit|hamster)\s+(?:named\s+)?([A-Za-z]+)?', msg_lower)
    if pet_match:
        pet = pet_match.group(1)
        pet_name = pet_match.group(2) if pet_match.group(2) else ""
        facts["pet"] = f"{pet}" + (f" named {pet_name}" if pet_name else "")
    
    # Favorite operator (Arknights)
    op_match = re.search(r'(?:favorite operator|main|like)\s+(?:is\s+)?([A-Za-z]+)', msg_lower)
    if op_match:
        facts["favorite_operator"] = op_match.group(1)
    
    # Nickname / handle
    nickname_match = re.search(r'(?:they call me|nickname is|go by)\s+([A-Za-z0-9]+)', user_message, re.IGNORECASE)
    if nickname_match:
        facts["nickname"] = nickname_match.group(1)
    
    return facts

def build_messages(user_message, memory):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if memory.get("facts"):
        facts_text = "Facts I remember:\n" + "\n".join([f"- {k}: {v}" for k, v in memory["facts"].items()])
        messages.append({"role": "system", "content": facts_text})
    
    for entry in memory["history"][-10:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["reply"]})
    
    messages.append({"role": "user", "content": user_message})
    return messages

def stream_chat(user_message):
    memory = load_memory()
    
    # Extract facts from user message
    new_facts = extract_facts(user_message)
    if new_facts:
        for key, value in new_facts.items():
            memory["facts"][key] = value
        save_memory(memory)
        print(f"📝 Extracted facts: {new_facts}")  # Debug print
    
    messages = build_messages(user_message, memory)
    
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