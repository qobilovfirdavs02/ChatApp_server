from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
from datetime import datetime
import asyncpg
from redis.asyncio import Redis
import logging
from typing import Dict, Optional
import asyncio
from database import get_db, get_redis

router = APIRouter()
active_connections: Dict[str, WebSocket] = {}
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Message Handler class to separate concerns
class MessageHandler:
    def __init__(self, db_pool: asyncpg.Pool, redis: Redis):
        self.db_pool = db_pool
        self.redis = redis

    async def get_cached_messages(self, cache_key: str) -> Optional[list]:
        cached = await self.redis.get(cache_key)
        return json.loads(cached) if cached else None

    async def fetch_db_messages(self, username: str, receiver: str) -> list:
        async with self.db_pool.acquire() as conn:
            messages = await conn.fetch("""
                SELECT id, sender_username, content, timestamp, edited, deleted, reaction, reply_to_id, type
                FROM messages 
                WHERE (sender_username = $1 AND receiver_username = $2) 
                   OR (sender_username = $2 AND receiver_username = $1)
                ORDER BY timestamp ASC
            """, username, receiver)
            return [{
                "msg_id": msg["id"],
                "sender": msg["sender_username"],
                "content": msg["content"] if not msg["deleted"] else "This message was deleted",
                "timestamp": msg["timestamp"].isoformat(),
                "edited": msg["edited"],
                "deleted": msg["deleted"],
                "reaction": msg["reaction"],
                "reply_to_id": msg["reply_to_id"],
                "type": msg["type"]
            } for msg in messages]

    async def update_cache(self, cache_key: str, messages: list):
        await self.redis.set(cache_key, json.dumps(messages), ex=3600)

# WebSocket Manager
class WebSocketManager:
    @staticmethod
    async def broadcast_message(receiver: str, message: dict):
        if receiver in active_connections:
            await active_connections[receiver].send_json(message)

    @staticmethod
    async def cleanup_connection(username: str):
        if username in active_connections:
            del active_connections[username]

# Action Handlers
async def handle_send(handler: MessageHandler, websocket: WebSocket, username: str, receiver: str, data: dict):
    content = data.get("content")
    reply_to_id = data.get("reply_to_id")
    
    if not content:
        await websocket.send_json({"error": "Content is required"})
        return

    async with handler.db_pool.acquire() as conn:
        msg_id = await conn.fetchval(
            "INSERT INTO messages (sender_username, receiver_username, content, reply_to_id, type) "
            "VALUES ($1, $2, $3, $4, 'text') RETURNING id",
            username, receiver, content, reply_to_id
        )
        
    msg = {
        "msg_id": msg_id,
        "sender": username,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "edited": False,
        "deleted": False,
        "reaction": None,
        "reply_to_id": reply_to_id,
        "type": "text"
    }
    
    # Update caches for both sender and receiver
    for user, other in [(username, receiver), (receiver, username)]:
        cache_key = f"messages:{user}:{other}"
        cached = await handler.get_cached_messages(cache_key)
        messages = cached or []
        messages.append(msg)
        await handler.update_cache(cache_key, messages)
    
    await WebSocketManager.broadcast_message(receiver, msg)
    await websocket.send_json(msg)

# Main WebSocket endpoint
@router.websocket("/ws/{username}/{receiver}")
async def websocket_endpoint(
    websocket: WebSocket,
    username: str,
    receiver: str,
    db_pool: asyncpg.Pool = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    # Prevent duplicate connections
    username = username.replace("%20", " ").strip()
    receiver = receiver.replace("%20", " ").strip()
    
    if username in active_connections:
        await websocket.close(code=1000, reason="Duplicate connection")
        return
        
    await websocket.accept()
    active_connections[username] = websocket
    logger.info(f"{username} connected")
    
    handler = MessageHandler(db_pool, redis)
    
    # Initial message load
    cache_key = f"messages:{username}:{receiver}"
    messages = await handler.get_cached_messages(cache_key)
    if not messages:
        messages = await handler.fetch_db_messages(username, receiver)
        await handler.update_cache(cache_key, messages)
    
    for msg in messages:
        await websocket.send_json(msg)

    # Action dispatcher
    action_handlers = {
        "send": handle_send,
        # Add other handlers (edit, delete, etc.) here as needed
    }

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            action = msg_data.get("action", "send")
            
            handler_func = action_handlers.get(action)
            if handler_func:
                await handler_func(handler, websocket, username, receiver, msg_data)
            else:
                await websocket.send_json({"error": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        logger.info(f"{username} disconnected")
        await WebSocketManager.cleanup_connection(username)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)
        await WebSocketManager.cleanup_connection(username)
        await websocket.close(code=1011, reason="Internal server error")

