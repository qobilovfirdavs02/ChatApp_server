# config.py
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# FastAPI ilovasini yaratish
app = FastAPI()

# CORS sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Agar faqat bitta client bo‘lsa, masalan: "http://192.168.99.253"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NeonDB ulanish sozlamalari
DB_PARAMS = {
    "dbname": "chatapp",
    "user": "neondb_owner",
    "password": "npg_IvTi7DPg2wOt",
    "host": "ep-restless-dawn-a80hwsr5-pooler.eastus2.azure.neon.tech",
    "port": "5432",
    "sslmode": "require"
}