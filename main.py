import uvicorn
from fastapi import FastAPI
from config import NEONDB_PARAMS, setup_cors
from database import init_db  # Jadval yaratish uchun
from routes import router  # Endpointlar uchun

app = FastAPI()

# CORS sozlamalarini o‘rnatish
setup_cors(app)

# Routerni qo‘shish
app.include_router(router)

# Dastur boshlanganda jadval yaratish
@app.on_event("startup")
async def startup_event():
    init_db()
    
@app.get("/")
async def root():
    return {"message": "Server va API ishlayapti!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
