from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
import os
import json
import requests

from core import stream_chat, load_memory, save_memory, get_greeting, check_search_availability

app = FastAPI()

CHAT_HISTORY_FILE = "memory/chat_history.json"
os.makedirs("memory", exist_ok=True)

_search_available_cache = None
_search_check_time = 0

def get_search_status():
    global _search_available_cache, _search_check_time
    import time
    
    if time.time() - _search_check_time > 300:
        _search_available_cache = check_search_availability()
        _search_check_time = time.time()
    
    return _search_available_cache

def load_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_chat_history(history):
    with open(CHAT_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def add_to_chat_history(role, message):
    history = load_chat_history()
    history.append({"role": role, "message": message})
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

@app.get("/search-status")
async def search_status():
    return {"available": get_search_status()}

@app.get("/history")
async def get_chat_history():
    return {"history": load_chat_history()}

@app.post("/clear")
async def clear_chat_history():
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
    add_to_chat_history("user", message)
    
    async def generate():
        full_reply = ""
        for chunk in stream_chat(message):
            full_reply += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        add_to_chat_history("assistant", full_reply)
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    print("\nVexra Server on http://localhost:8000")
    print("Chat history shared across all devices\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)