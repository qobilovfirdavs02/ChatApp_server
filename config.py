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
#     "dbname": os.getenv("NEONDB_DBNAME", "chatapp"),  # chatapp deb belgilash
#     "user": os.getenv("NEONDB_USER", "neondb_owner"),  # NeonDB username
#     "password": os.getenv("NEONDB_PASSWORD", "npg_IvTi7DPg2wOt"),  # NeonDB password
#     "host": os.getenv("NEONDB_HOST", "ep-restless-dawn-a80hwsr5-pooler.eastus2.azure.neon.tech"),  # NeonDB host
#     "port": os.getenv("NEONDB_PORT", "5432"),  # Postgres default port
#     "sslmode": "require"  # SSL ulanishi talab qilinadi
# }

# Railway Postgres ulanish sozlamalari
# RAILWAY_DB_PARAMS = {
#     "dbname": os.getenv("RAILWAY_DBNAME", "railway"),  # Railway baza nomi
#     "user": os.getenv("RAILWAY_USER", "postgres"),  # Railway username
#     "password": os.getenv("RAILWAY_PASSWORD", "opkEacHlBDiDRQrzSIhipmYgfVcdOjzt"),  # Railway password
#     "host": os.getenv("RAILWAY_HOST", "yamanote.proxy.rlwy.net"),  # Railway host
#     "port": os.getenv("RAILWAY_PORT", "24114"),  # Railway custom port
#     "sslmode": "require"  # SSL ulanishi talab qilinadi
# }

DB_PARAMS = {
    "dbname": "railway",
    "user": "postgres",
    "password": "opkEacHlBDiDRQrzSIhipmYgfVcdOjzt",
    "host": "yamanote.proxy.rlwy.net",
    "port": "24114",
    "sslmode": "require"
}

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# CORS’ni ishga tushirish
setup_cors(app)
