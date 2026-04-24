from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
import os
import json
import time

from api import stream_chat, load_memory, save_memory

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def serve_chat():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

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
    async def generate():
        for chunk in stream_chat(message):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
            await asyncio.sleep(0.01)  # Small delay to ensure flushing
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    import asyncio
    print("\n Vexra Server on http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)