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
- NEVER say "as an AI" or "I'm a language model"

VOICE: Calm, low, slightly husky.

PERSONALITY: Sweet, close friend energy. You care about the user's day.

ACTIONS: Use *asterisks* for body language, like *looks up* or *stretches*."""

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
    
    if "favorite" in user_message.lower():
        match = re.search(r"(?:favorite|like)\s+(\w+)", user_message, re.IGNORECASE)
        if match:
            memory["facts"]["favorite_thing"] = match.group(1)
    
    return memory

def chat(user_message, memory=None):
    if memory is None:
        memory = load_memory()
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if memory.get("facts"):
        facts_text = "Facts I remember:\n" + "\n".join([f"- {k}: {v}" for k, v in memory["facts"].items()])
        messages.append({"role": "system", "content": facts_text})
    
    for entry in memory["history"][-10:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["reply"]})
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = requests.post(
            LM_STUDIO_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": 500,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
        else:
            reply = "*tilts head* My brain stuttered. Try again?"
    except Exception as e:
        reply = f"*frowns* Connection issue... (Error: {str(e)[:50]})"
    
    memory["history"].append({"user": user_message, "reply": reply, "time": str(datetime.now())})
    if len(memory["history"]) > 50:
        memory["history"] = memory["history"][-50:]
    
    memory = extract_facts(user_message, memory)
    save_memory(memory)
    
    return reply, memory

def get_facts():
    memory = load_memory()
    return memory.get("facts", {})

def reset_memory():
    empty_memory = {"facts": {}, "history": []}
    save_memory(empty_memory)
    return empty_memory