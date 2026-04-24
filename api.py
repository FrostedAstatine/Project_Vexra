import requests
import json
import os
import re
from datetime import datetime
import hashlib

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-4b-instruct-2507"
MEMORY_FILE = "vexra_memory.json"
LONG_TERM_FILE = "long_term_memory.json"

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

def load_long_term():
    if os.path.exists(LONG_TERM_FILE):
        with open(LONG_TERM_FILE, 'r') as f:
            return json.load(f)
    return {"memories": []}

def save_long_term(long_term):
    with open(LONG_TERM_FILE, 'w') as f:
        json.dump(long_term, f, indent=2)

def extract_keywords(text):
    """Extract important keywords from text for matching"""
    text_lower = text.lower()
    keywords = []
    
    # Important word categories
    time_words = ['yesterday', 'last week', 'last month', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    topic_words = ['exam', 'test', 'work', 'job', 'school', 'cat', 'dog', 'pet', 'game', 'movie', 'anime', 'arknights']
    feeling_words = ['stressed', 'happy', 'sad', 'excited', 'worried', 'tired']
    
    for word in time_words + topic_words + feeling_words:
        if word in text_lower:
            keywords.append(word)
    
    return keywords

def add_to_long_term_memory(user_message, assistant_reply):
    """Store conversation with keywords for later recall"""
    long_term = load_long_term()
    
    keywords = extract_keywords(user_message)
    
    long_term["memories"].append({
        "user_message": user_message,
        "assistant_reply": assistant_reply[:500],
        "keywords": keywords,
        "timestamp": datetime.now().isoformat(),
        "id": hashlib.md5(f"{user_message}{datetime.now()}".encode()).hexdigest()[:8]
    })
    
    # Keep only last 200 memories
    if len(long_term["memories"]) > 200:
        long_term["memories"] = long_term["memories"][-200:]
    
    save_long_term(long_term)

def search_long_term_memory(user_message):
    """Find relevant past conversations by keyword matching"""
    long_term = load_long_term()
    user_keywords = extract_keywords(user_message)
    
    if not user_keywords:
        return []
    
    relevant = []
    for memory in long_term["memories"][-50:]:  # Search last 50 memories
        if any(kw in memory["keywords"] for kw in user_keywords):
            relevant.append(memory)
    
    # Return only last 2 relevant memories
    return relevant[-2:]

def extract_facts(user_message):
    facts = {}
    msg_lower = user_message.lower()
    
    age_match = re.search(r'(?:i am|i\'m|age) (\d{1,3})(?:\s|\.|$)', msg_lower)
    if age_match:
        facts["age"] = age_match.group(1)
    
    name_patterns = [
        r'(?:my name is|i am|i\'m|call me)\s+([A-Za-z][A-Za-z0-9]+)',
        r'(?:they call me)\s+([A-Za-z][A-Za-z0-9]+)',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            name = match.group(1)
            if len(name) > 1 and name.lower() not in ['im', 'i\'m']:
                facts["name"] = name
                break
    
    nickname_match = re.search(r'(?:they call me|nickname is|go by)\s+([A-Za-z0-9]+)', user_message, re.IGNORECASE)
    if nickname_match:
        facts["nickname"] = nickname_match.group(1)
    
    return facts

def build_messages(user_message, memory):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Search long-term memory for relevant past conversations
    relevant_memories = search_long_term_memory(user_message)
    if relevant_memories:
        context = "Relevant past conversations you had with the user:\n"
        for mem in relevant_memories:
            context += f"- User previously said: {mem['user_message'][:150]}\n"
            context += f"  You replied: {mem['assistant_reply'][:150]}\n"
        messages.append({"role": "system", "content": context})
    
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
    
    new_facts = extract_facts(user_message)
    if new_facts:
        for key, value in new_facts.items():
            memory["facts"][key] = value
        save_memory(memory)
        print(f"📝 Facts: {new_facts}")
    
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
    
    add_to_long_term_memory(user_message, full_reply)
    
    memory["history"].append({"user": user_message, "reply": full_reply, "time": str(datetime.now())})
    if len(memory["history"]) > 50:
        memory["history"] = memory["history"][-50:]
    
    save_memory(memory)