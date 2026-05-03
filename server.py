from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
import os
import json

from core import stream_chat, load_memory, save_memory, get_greeting

app = FastAPI()

CHAT_HISTORY_FILE = "memory/chat_history.json"

# Ensure memory directory exists
os.makedirs("memory", exist_ok=True)

def load_chat_history():
    """Load shared chat history from server"""
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_chat_history(history):
    """Save shared chat history to server"""
    with open(CHAT_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def add_to_chat_history(role, message):
    """Add a message to shared history"""
    history = load_chat_history()
    history.append({"role": role, "message": message})
    # Keep last 200 messages to prevent file bloat
    if len(history) > 200:
        history = history[-200:]
    save_chat_history(history)

@app.get("/", response_class=HTMLResponse)
async def serve_chat():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
            greeting = get_greeting()
            html = html.replace("__GREETING__", greeting)
            return HTMLResponse(content=html)
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

@app.get("/history")
async def get_chat_history():
    """Get all chat history (for page load)"""
    return {"history": load_chat_history()}

@app.post("/clear")
async def clear_chat_history():
    """Clear all chat history"""
    save_chat_history([])
    return {"status": "cleared"}

@app.get("/greeting")
async def get_greeting_endpoint():
    return {"greeting": get_greeting()}

@app.get("/facts")
async def get_facts():
    memory = load_memory()
    return {"facts": memory.get("facts", {})}

@app.post("/reset")
async def reset_memory():
    empty_memory = {"facts": {}, "history": []}
    save_memory(empty_memory)
    return {"status": "reset"}

@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    # Add user message to shared history
    add_to_chat_history("user", message)
    
    async def generate():
        full_reply = ""
        for chunk in stream_chat(message):
            full_reply += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        # Add assistant reply to shared history after streaming completes
        add_to_chat_history("assistant", full_reply)
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    print("\n Vexra Server on http://localhost:8000")
    print(" Chat history shared across all devices\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)