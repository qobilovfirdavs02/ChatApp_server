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


# database.py
from fastapi import Depends
from redis.asyncio import Redis
import asyncpg
import os
from typing import AsyncGenerator
from config import NEONDB_PARAMS
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# NeonDB connection
async def get_db() -> AsyncGenerator[asyncpg.Pool, None]:
    try:
        pool = await asyncpg.create_pool(**NEONDB_PARAMS)
        logger.info("NeonDB pool successfully created")
        yield pool
    except Exception as e:
        logger.error(f"Failed to connect to NeonDB: {str(e)}", exc_info=True)
        raise
    finally:
        await pool.close()
        logger.info("NeonDB pool closed")

# Redis connection
async def get_redis() -> AsyncGenerator[Redis, None]:
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = await Redis.from_url(REDIS_URL)
    try:
        yield redis
    finally:
        await redis.close()



