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


PORT = os.getenv("PORT", "8000")  # Default 8000
PORT = int(PORT) if PORT.isdigit() else 8000  # Xato bo'lsa 8000 ni ishlatish

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)

