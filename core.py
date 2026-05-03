import requests
import json
import os
import re
import urllib.parse
import time
from datetime import datetime
from bs4 import BeautifulSoup

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-4b-instruct-2507"
MEMORY_FILE = "memory/vexra_memory.json"
PERSONA_FILE = "persona.json"

os.makedirs("memory", exist_ok=True)

_search_available_cache = None
_search_check_time = 0

def check_search_availability():
    global _search_available_cache, _search_check_time
    
    if time.time() - _search_check_time < 300 and _search_available_cache is not None:
        return _search_available_cache
    
    try:
        test_url = "https://en.wikipedia.org/api/rest_v1/summary/test"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            print("Wikipedia reachable")
            _search_available_cache = True
            _search_check_time = time.time()
            return True
    except:
        pass
    
    try:
        test_url = "https://lite.duckduckgo.com/lite/"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            print("DuckDuckGo reachable")
            _search_available_cache = True
            _search_check_time = time.time()
            return True
    except:
        pass
    
    print("No search engine reachable")
    _search_available_cache = False
    _search_check_time = time.time()
    return False

def load_persona():
    default_persona = {
        "name": "Vexra",
        "greeting": "*looks up* Hey.",
        "voice": "Calm and warm",
        "personality": "Friendly and caring",
        "interests": [],
        "rules": [
            "Never use emojis",
            "Never mention AI or being digital",
            "Use *asterisks* for body language",
            "You are NOT an expert. Your knowledge has gaps.",
            "Never invent lore or characters that don't exist"
        ],
        "facts": {}
    }
    
    if os.path.exists(PERSONA_FILE):
        with open(PERSONA_FILE, 'r', encoding='utf-8') as f:
            persona = json.load(f)
            for key, value in default_persona.items():
                if key not in persona:
                    persona[key] = value
            return persona
    return default_persona

def get_system_prompt(persona):
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

def web_search(query):
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        results = []
        for item in data['query']['search'][:3]:
            title = item['title']
            snippet = re.sub(r'<[^>]+>', '', item.get('snippet', ''))
            results.append(f"- {title}: {snippet[:200]}...")
        
        if results:
            return "\n".join(results)
        return None
    except Exception as e:
        print(f"Wikipedia search error: {e}")
        return None

def check_if_search_needed(user_message, memory, persona):
    system_prompt = get_system_prompt(persona)
    
    recent_history = memory["history"][-5:] if memory.get("history") else []
    
    context = ""
    for entry in recent_history:
        context += f"User: {entry['user']}\nVexra: {entry['reply']}\n"
    
    prompt = f"""You are {persona['name']}. You are having a conversation with the user.

Recent conversation:
{context}

The user just said: "{user_message}"

Do you need to search the web to respond properly?

YOU SHOULD SEARCH IF:
- The user asks about a specific person, character, event, or fact
- You are not 100 percent certain about your answer
- You would need to guess or make up facts

ONLY say NO SEARCH if:
- It's a casual greeting like hi or how are you
- The user is sharing personal feelings or opinions

When in doubt, SEARCH. Better to search than to give wrong information.

Respond with EXACTLY one line:

SEARCH: your search query here
or
NO SEARCH"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = requests.post(
            LM_STUDIO_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 100,
                "stream": False
            },
            timeout=15
        )
        
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            print(f"Vexra says: {reply[:80]}")
            
            search_match = re.search(r'SEARCH:\s*(.+?)(?:\n|$)', reply, re.IGNORECASE)
            if search_match:
                query = search_match.group(1).strip()
                print(f"Vexra wants to search for: '{query}'")
                return query
            
            if re.search(r'NO SEARCH', reply, re.IGNORECASE):
                print("Vexra decided: No search needed")
                return None
        
        return None
        
    except Exception as e:
        print(f"Search check error: {e}")
        return None

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
    
    name_match = re.search(r'(?:my name is|i am|i\'m|call me)\s+([A-Za-z][A-Za-z0-9]+)', user_message, re.IGNORECASE)
    if name_match:
        name = name_match.group(1)
        if len(name) > 1 and name.lower() not in ['im', 'i\'m']:
            memory["facts"]["name"] = name
    
    return memory

def build_messages(user_message, memory, persona, search_results=None):
    messages = [{"role": "system", "content": get_system_prompt(persona)}]
    
    if search_results:
        messages.append({"role": "system", "content": f"WEB SEARCH RESULTS:\n{search_results}\n\nUse this information to answer accurately. Do not make up facts."})
    
    if memory.get("facts"):
        facts_text = "Facts I remember:\n" + "\n".join([f"- {k}: {v}" for k, v in memory["facts"].items()])
        messages.append({"role": "system", "content": facts_text})
    
    for entry in memory["history"][-10:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["reply"]})
    
    messages.append({"role": "user", "content": user_message})
    return messages

def stream_chat(user_message):
    print(f"\nUSER: {user_message}")
    
    persona = load_persona()
    memory = load_memory()
    
    memory = extract_facts(user_message, memory)
    
    search_available = check_search_availability()
    
    search_results = None
    if search_available:
        print("Search available, checking if needed...")
        search_query = check_if_search_needed(user_message, memory, persona)
        
        if search_query:
            print(f"Executing search for: '{search_query}'")
            search_results = web_search(search_query)
            if search_results:
                print("SEARCH RESULTS FOUND")
            else:
                print("No search results found")
        else:
            print("Search not triggered")
    else:
        print("Search unavailable skipping search decision")
    
    messages = build_messages(user_message, memory, persona, search_results)
    
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
    
    print(f"VEXRA REPLY LENGTH: {len(full_reply)} chars")
    
    memory["history"].append({"user": user_message, "reply": full_reply, "time": str(datetime.now())})
    if len(memory["history"]) > 50:
        memory["history"] = memory["history"][-50:]
    
    save_memory(memory)