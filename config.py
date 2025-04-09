import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# FastAPI ilovasini yaratish
app = FastAPI()

load_dotenv()

# CORS sozlamalari
def setup_cors(app):
    app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Agar faqat bitta client bo‘lsa, masalan: "http://192.168.99.253"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NeonDB ulanish sozlamalari


# NEONDB_PARAMS = {
#     "dbname": os.getenv("NEONDB_DBNAME", "chatapp"),
#     "user": os.getenv("NEONDB_USER", "neondb_owner"),
#     "password": os.getenv("NEONDB_PASSWORD", "npg_IvTi7DPg2wOt"),
#     "host": os.getenv("NEONDB_HOST", "ep-restless-dawn-a80hwsr5-pooler.eastus2.azure.neon.tech"),
#     "port": os.getenv("NEONDB_PORT", "5432"),
#     "sslmode": os.getenv("NEONDB_SSLMODE", "require"),
# }
# NEONDB_PARAMS = {
#     "database": os.getenv("NEONDB_DBNAME", "chatapp"),
#     "user": os.getenv("NEONDB_USER", "neondb_owner"),
#     "password": os.getenv("NEONDB_PASSWORD", "npg_IvTi7DPg2wOt"),
#     "host": os.getenv("NEONDB_HOST", "ep-restless-dawn-a80hwsr5-pooler.eastus2.azure.neon.tech"),
#     "port": int(os.getenv("NEONDB_PORT", "5432")),  # string emas, int
#     "ssl": True  # NeonDB SSL talab qiladi
# }
# config.py


NEONDB_PARAMS = {
    "dbname": os.getenv("NEONDB_DBNAME", "chatapp"),
    "user": os.getenv("NEONDB_USER", "neondb_owner"),
    "password": os.getenv("NEONDB_PASSWORD", "npg_IvTi7DPg2wOt"),
    "host": os.getenv("NEONDB_HOST", "ep-restless-dawn-a80hwsr5-pooler.eastus2.azure.neon.tech"),
    "port": os.getenv("NEONDB_PORT", "5432"),
    "sslmode": os.getenv("NEONDB_SSLMODE", "require"),
}

# Railway Postgres ulanish sozlamalari
# RAILWAY_DB_PARAMS = {
#     "dbname": os.getenv("RAILWAY_DBNAME", "railway"),  # Railway baza nomi
#     "user": os.getenv("RAILWAY_USER", "postgres"),  # Railway username
#     "password": os.getenv("RAILWAY_PASSWORD", "opkEacHlBDiDRQrzSIhipmYgfVcdOjzt"),  # Railway password
#     "host": os.getenv("RAILWAY_HOST", "yamanote.proxy.rlwy.net"),  # Railway host
#     "port": os.getenv("RAILWAY_PORT", "24114"),  # Railway custom port
#     "sslmode": "require"  # SSL ulanishi talab qilinadi
# }



CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# CORS’ni ishga tushirish
setup_cors(app)
