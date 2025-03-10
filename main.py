# main.py
import uvicorn
from fastapi import FastAPI
from config import DB_PARAMS, setup_cors
from database import *  # Jadval yaratish uchun
from routes import *   # Endpointlar uchun
import psycopg2 # Endpointlar uchun



app = FastAPI()
setup_cors(app)

def get_db():
    conn = psycopg2.connect(**DB_PARAMS)
    return conn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # uvicorn main:app --host 0.0.0.0 --port 8000 --reload