import uvicorn
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

# Port va hostni qo'lda belgilash
PORT = 8000  # Manual port, qo'lda belgilash
HOST = "0.0.0.0"

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
