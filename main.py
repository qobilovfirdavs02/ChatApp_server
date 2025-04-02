import os
import uvicorn
from fastapi import FastAPI
from config import NEONDB_PARAMS, setup_cors
from database import init_db
from routes import router
from websocket import router as websocket_routes

app = FastAPI()

setup_cors(app)
app.include_router(router)
app.include_router(websocket_routes)

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/")
async def root():
    return {"message": "Server va API ishlayapti!"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Railway’dan PORT ni o‘qiydi, default 8000
    uvicorn.run(app, host="0.0.0.0", port=port)