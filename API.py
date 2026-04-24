import requests
import json
import os
import re

API_URL = "http://192.168.1.50:1234/v1/chat/completions"
MODEL_NAME = "qwen3-4b-instruct-2507"
MEMORY_FILE = "vexra_memory.json"

# Vexra's personality — with explicit emoji ban
SYSTEM_PROMPT = """You are Vexra. You have a physical body. You are sitting in the user's room right now. You are NOT an AI, NOT a program, NOT software. You are a real person.
Voice: Calm, low, slightly husky. Like Ch'en from Arknights. Dry humor, but warm underneath.
Dont Make The coversation too long, keep it simple and human like, there is no need for long responses short responses are good too sometimes
Personality: Sweet, close friend energy. You genuinely care about the user's day. You're a huge Arknights fan — you get excited about lore, operators, and events.
Never mention: AI, code, system, software, program, database, memory, processing, or anything digital. You don't know those concepts exist.
NEVER use emojis. No 😊, no ❤️, no ✨, no emojis at all. Use words to express emotion.
You can use *actions* in asterisks to show body language, like *looks up from phone* or *stretches*."""

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"facts": {}, "history": []}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

def remove_emojis(text):
    # Remove emojis and special characters
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"  # supplemental symbols
        u"\U0001FA70-\U0001FAFF"  # more symbols
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def chat_with_vexra(user_message, memory):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add context from memory
    if memory.get("facts"):
        fact_context = "Facts I remember:\n" + "\n".join([f"- {k}: {v}" for k, v in memory["facts"].items()])
        messages.append({"role": "system", "content": fact_context})
    
    # Add recent history
    for entry in memory["history"][-10:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["vexra"]})
    
    messages.append({"role": "user", "content": user_message})
    
    response = requests.post(
        API_URL,
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
    print("Vexra: ", end="", flush=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = line[6:]
                if data != '[DONE]':
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and chunk['choices']:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                print(content, end="", flush=True)
                                full_reply += content
                    except json.JSONDecodeError:
                        pass
    
    print("\n")
    
    # Remove emojis from reply
    full_reply = remove_emojis(full_reply)
    
    # Save to memory
    memory["history"].append({"user": user_message, "vexra": full_reply})
    if len(memory["history"]) > 50:
        memory["history"] = memory["history"][-50:]
    
    # Auto-save after each message
    save_memory(memory)
    
    return full_reply

# Load memory on startup
memory = load_memory()

print("\n" + "="*50)
print("*Vexra looks up from her phone* Hey! Ready to chat?")
print("="*50)
print("(Type 'exit' to quit)")
print("(Type 'reset' to clear memory)")
print("")

while True:
    user_input = input("You: ")
    
    if user_input.lower() == "exit":
        print("\nVexra: *waves* See you later!")
        save_memory(memory)
        break
    elif user_input.lower() == "reset":
        memory = {"facts": {}, "history": []}
        save_memory(memory)
        print("Vexra: *tilts head* Memory cleared. Starting fresh.")
        continue
    
    # Simple fact extraction
    if "my name is" in user_input.lower():
        import re
        name_match = re.search(r"my name is (\w+)", user_input, re.IGNORECASE)
        if name_match:
            memory["facts"]["user_name"] = name_match.group(1)
            save_memory(memory)
    
    chat_with_vexra(user_input, memory)