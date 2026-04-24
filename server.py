from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import os

from api import chat, get_facts, reset_memory

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def serve_chat():
    html_path = os.path.join(os.path.dirname(file), "index.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

@app.get("/facts")
async def get_facts_endpoint():
    return {"facts": get_facts()}

@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    reply, memory = chat(message)
    return {"reply": reply, "facts": memory.get("facts", {})}

@app.post("/reset")
async def reset_memory_endpoint():
    reset_memory()
    return {"status": "reset"}

if name == "main":
    import uvicorn
    print("\n Vexra Server on http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)