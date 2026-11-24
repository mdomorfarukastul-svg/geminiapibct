import os
import base64
from typing import Optional, List
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Gemini Hybrid GET & POST JSON API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_NEW_GEMINI_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class FileAttachment(BaseModel):
    mime_type: str                     # যেমন: "image/jpeg", "application/pdf", "audio/mp3"
    base64_data: Optional[str] = None
    file_url: Optional[str] = None

class ChatRequest(BaseModel):
    text: str
    model: str = "gemini-flash-latest"
    files: Optional[List[FileAttachment]] = None

async def call_gemini_api(parts: list, model: str):
    if not API_KEY or API_KEY == "YOUR_NEW_GEMINI_API_KEY":
        raise HTTPException(status_code=500, detail="Vercel-এ GEMINI_API_KEY সেট করা হয়নি।")

    url = f"{BASE_URL}/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": API_KEY
    }
    payload = {"contents": [{"parts": parts}]}

    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            data = response.json()

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=data)

            reply = data["candidates"][0]["content"]["parts"][0]["text"]
            return {
                "status": "success",
                "model": model,
                "reply": reply
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"API ত্রুটি: {str(e)}")

@app.get("/")
def home():
    return {
        "status": "online",
        "text_only_usage": "GET /api/chat?text=Hello",
        "file_with_text_usage": "POST /api/chat (with JSON body)"
    }

# ১. শুধু টেক্সটের জন্য GET ফরম্যাট (JSON বডি লাগবে না)
@app.get("/api/chat")
async def chat_get(
    text: str = Query(..., description="আপনার প্রশ্ন বা প্রম্পট লিখুন"),
    model: str = Query("gemini-flash-latest", description="Gemini মডেলের নাম")
):
    parts = [{"text": text}]
    return await call_gemini_api(parts, model)

# ২. ফাইল ও টেক্সট একসাথে পাঠানোর জন্য POST JSON বডি ফরম্যাট
@app.post("/api/chat")
async def chat_post(req: ChatRequest):
    parts = [{"text": req.text}]

    if req.files:
        async with httpx.AsyncClient(timeout=45.0) as client:
            for item in req.files:
                if item.base64_data:
                    clean_b64 = item.base64_data.split(",")[-1]
                    parts.append({
                        "inlineData": {
                            "mimeType": item.mime_type,
                            "data": clean_b64
                        }
                    })
                elif item.file_url:
                    try:
                        res = await client.get(item.file_url)
                        res.raise_for_status()
                        encoded = base64.b64encode(res.content).decode("utf-8")
                        parts.append({
                            "inlineData": {
                                "mimeType": item.mime_type,
                                "data": encoded
                            }
                        })
                    except Exception as e:
                        raise HTTPException(status_code=400, detail=f"ফাইল ডাউনলোড ব্যর্থ: {str(e)}")

    return await call_gemini_api(parts, req.model)
