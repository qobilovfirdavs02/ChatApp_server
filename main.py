# main.py
import uvicorn
from config import app
from database import *  # Jadval yaratish uchun
from routes import *   # Endpointlar uchun

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # uvicorn main:app --host 0.0.0.0 --port 8000 --reload