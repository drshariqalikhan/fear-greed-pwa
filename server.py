import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import fear_greed

app = FastAPI(title="CNN Fear & Greed Single-File PWA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/get")
def api_get():
    return fear_greed.get()

@app.get("/api/score")
def api_score():
    return {"score": fear_greed.get_score()}

@app.get("/api/rating")
def api_rating():
    return {"rating": fear_greed.get_rating()}

@app.get("/api/history")
def api_history(last: str = Query(default="30d"), start: str = None, end: str = None):
    kwargs = {}
    if last: kwargs["last"] = last
    if start: kwargs["start"] = start
    if end: kwargs["end"] = end
    return fear_greed.get_history(**kwargs)

@app.get("/api/raw")
def api_raw():
    return fear_greed.fetch()

# Serve the single-file PWA for the root route and fallback
@app.get("/")
def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)