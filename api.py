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

def extract_facts(user_message, memory):
    if "my name is" in user_message.lower():
        match = re.search(r"my name is (\w+)", user_message, re.IGNORECASE)
        if match:
            memory["facts"]["user_name"] = match.group(1)
    return memory

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
    memory = extract_facts(user_message, memory)
    save_memory(memory)