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
from config import app, NEONDB_PARAMS
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

NEONDB_PARAMS = {
    "database": os.getenv("NEONDB_DBNAME", "chatapp"),
    "user": os.getenv("NEONDB_USER", "neondb_owner"),
    "password": os.getenv("NEONDB_PASSWORD", "npg_IvTi7DPg2wOt"),
    "host": os.getenv("NEONDB_HOST", "ep-restless-dawn-a80hwsr5-pooler.eastus2.azure.neon.tech"),
    "port": os.getenv("NEONDB_PORT", "5432"),
    "ssl": True
}

async def get_db():
    conn = await asyncpg.connect(**NEONDB_PARAMS)
    logger.info(f"DB connection type: {type(conn)}")
    try:
        yield conn
    finally:
        await conn.close()

async def get_redis():
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = await Redis.from_url(REDIS_URL)
    try:
        yield redis
    finally:
        await redis.close()

async def init_db():
    async with asyncpg.connect(**NEONDB_PARAMS) as conn:
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
        logger.info("Jadvallar yaratildi yoki allaqachon mavjud.")

@app.on_event("startup")
async def startup_event():
    await init_db()