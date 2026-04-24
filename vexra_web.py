from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
import json
import os
from datetime import datetime
import re

# --- Configuration ---
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-4b-instruct-2507"
MEMORY_FILE = "vexra_memory.json"

# --- FastAPI Setup ---
app = FastAPI(title="Vexra Web", description="Your AI companion")
templates = Jinja2Templates(directory="templates")

# --- Memory Functions ---
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"facts": {}, "history": []}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

# --- Vexra's Brain ---
def chat_with_vexra(user_message, memory):
    # Build system prompt (no emojis!)
    system_prompt = """You are Vexra. You have a physical body. You are in the user's room.

NEVER use emojis. NEVER mention AI, code, or being software.

Voice: Calm, low, slightly husky. Like Ch'en from Arknights.

You CAN use *actions* like *looks up* or *stretches*."""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add facts from memory
    if memory.get("facts"):
        fact_context = "Facts I remember:\n" + "\n".join([f"- {k}: {v}" for k,v in memory["facts"].items()])
        messages.append({"role": "system", "content": fact_context})
    
    # Add chat history
    for entry in memory["history"][-10:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["vexra"]})
    
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
            reply = "*tilts head* Hmm, my brain stuttered. Try again?"
    except Exception as e:
        reply = f"*frowns* Something's off... (Error: {str(e)[:50]})"
    
    # Save to memory
    memory["history"].append({"user": user_message, "vexra": reply, "time": str(datetime.now())})
    if len(memory["history"]) > 50:
        memory["history"] = memory["history"][-50:]
    
    # Auto-save and extract facts
    if "my name is" in user_message.lower():
        name_match = re.search(r"my name is (\w+)", user_message, re.IGNORECASE)
        if name_match:
            memory["facts"]["user_name"] = name_match.group(1)
    
    save_memory(memory)
    
    return reply

# --- Web Routes ---
@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):
    # Load existing memory to show facts
    memory = load_memory()
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "facts": memory.get("facts", {})
    })

@app.post("/send")
async def send_message(message: str = Form(...)):
    memory = load_memory()
    reply = chat_with_vexra(message, memory)
    return {"reply": reply, "facts": memory.get("facts", {})}

# --- Run the Server ---
if __name__ == "main":
    import uvicorn
    print("\n" + "="*50)
    print("🌟 Vexra Web Server Starting...")
    print("="*50)
    print("\n📱 Access from your phone:")
    print("   http://[YOUR_PC_IP]:8000")
    print("\n💻 Access from this computer:")
    print("   http://localhost:8000")
    print("\n🚀 Press Ctrl+C to stop")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)