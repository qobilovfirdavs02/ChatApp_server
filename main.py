import uvicorn
import os
from fastapi import FastAPI
from config import NEONDB_PARAMS, setup_cors
from database import init_db  # Jadval yaratish uchun
from routes import router # Endpointlar uchun
from websocket import router as websocket_routes

app = FastAPI()

# CORS sozlamalarini o‘rnatish
setup_cors(app)

# Routerni qo‘shish
app.include_router(router)
app.include_router(websocket_routes)

# Dastur boshlanganda jadval yaratish
@app.on_event("startup")
async def startup_event():
    init_db()
    
@app.get("/")
async def root():
    return {"message": "Server va API ishlayapti!"}


PORT = os.getenv("PORT")
if PORT is None or not PORT.isdigit():
    PORT = 8000  # Default port agar PORT noto‘g‘ri bo‘lsa

PORT = int(PORT)

