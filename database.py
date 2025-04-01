# database.py
import psycopg2
from psycopg2.extras import RealDictCursor
from config import NEONDB_PARAMS, app

def get_db():
    conn = psycopg2.connect(**NEONDB_PARAMS, cursor_factory=RealDictCursor)
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        # Users jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(100) UNIQUE,
                password VARCHAR(256),
                reset_code VARCHAR(6)
            )
        """)
        # Messages jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender_username VARCHAR(255) NOT NULL,
    receiver_username VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited BOOLEAN DEFAULT FALSE,
    deleted BOOLEAN DEFAULT FALSE,
    reaction VARCHAR(50),
    reply_to_id INT,
    FOREIGN KEY (reply_to_id) REFERENCES messages(id) ON DELETE SET NULL
            )
        """)
        conn.commit()
        print("Jadvallar yaratildi yoki allaqachon mavjud.")

@app.on_event("startup")
async def startup_event():
    init_db()