# import psycopg2
# from psycopg2.extras import RealDictCursor
# from config import NEONDB_PARAMS, app
# from redis.asyncio import Redis  # aioredis o‘rniga redis.asyncio
# import os

# # NeonDB (PostgreSQL) konfiguratsiyasi
# def get_db():
#     conn = psycopg2.connect(**NEONDB_PARAMS, cursor_factory=RealDictCursor)
#     return conn

# # Redis konfiguratsiyasi
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# async def get_redis():
#     redis = await Redis.from_url(REDIS_URL)  # Redis.from_url ishlatiladi
#     try:
#         yield redis
#     finally:
#         await redis.close()

# def init_db():
#     with get_db() as conn:
#         cursor = conn.cursor()
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id SERIAL PRIMARY KEY,
#                 username VARCHAR(50) UNIQUE,
#                 email VARCHAR(100) UNIQUE,
#                 password VARCHAR(256),
#                 reset_code VARCHAR(6)
#             )
#         """)
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS messages (
#                 id SERIAL PRIMARY KEY,
#                 sender_username VARCHAR(255) NOT NULL,
#                 receiver_username VARCHAR(255) NOT NULL,
#                 content TEXT NOT NULL,
#                 timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                 edited BOOLEAN DEFAULT FALSE,
#                 deleted BOOLEAN DEFAULT FALSE,
#                 reaction VARCHAR(50),
#                 reply_to_id INT,
#                 FOREIGN KEY (reply_to_id) REFERENCES messages(id) ON DELETE SET NULL
#             )
#         """)
#         conn.commit()
#         print("Jadvallar yaratildi yoki allaqachon mavjud.")

# @app.on_event("startup")
# async def startup_event():
#     init_db()

import asyncpg
from fastapi import Depends
import os
from config import NEONDB_PARAMS, app

# NeonDB (PostgreSQL) konfiguratsiyasi
async def get_db():
    # Agar NEONDB_PARAMS ishlatilsa, uni asyncpg bilan moslashtiramiz
    conn = await asyncpg.connect(
        user=NEONDB_PARAMS.get("user"),
        password=NEONDB_PARAMS.get("password"),
        database=NEONDB_PARAMS.get("dbname"),
        host=NEONDB_PARAMS.get("host"),
        port=NEONDB_PARAMS.get("port")
    )
    try:
        yield conn
    finally:
        await conn.close()

# Agar Railway’da DATABASE_URL ishlatmoqchi bo‘lsangiz, quyidagini ishlatishingiz mumkin:
# async def get_db():
#     conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
#     try:
#         yield conn
#     finally:
#         await conn.close()

# Redis konfiguratsiyasi
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def get_redis():
    redis = await Redis.from_url(REDIS_URL)
    try:
        yield redis
    finally:
        await redis.close()

# Jadvallarni yaratish uchun sinxron init_db ni asinxron qilamiz
async def init_db():
    async with asyncpg.connect(
        user=NEONDB_PARAMS.get("user"),
        password=NEONDB_PARAMS.get("password"),
        database=NEONDB_PARAMS.get("dbname"),
        host=NEONDB_PARAMS.get("host"),
        port=NEONDB_PARAMS.get("port")
    ) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(100) UNIQUE,
                password VARCHAR(256),
                reset_code VARCHAR(6)
            )
        """)
        await conn.execute("""
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
                type VARCHAR(50) DEFAULT 'text',
                FOREIGN KEY (reply_to_id) REFERENCES messages(id) ON DELETE SET NULL
            )
        """)
        print("Jadvallar yaratildi yoki allaqachon mavjud.")

@app.on_event("startup")
async def startup_event():
    await init_db()