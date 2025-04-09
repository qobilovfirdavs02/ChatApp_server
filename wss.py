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
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Message Handler class
class MessageHandler:
    def __init__(self, db_pool: asyncpg.Pool, redis: Redis):
        self.db_pool = db_pool
        self.redis = redis

    async def get_cached_messages(self, cache_key: str) -> Optional[list]:
        cached = await self.redis.get(cache_key)
        if cached:
            logger.info(f"Cache hit for {cache_key}")
            return json.loads(cached)
        logger.info(f"Cache miss for {cache_key}")
        return None

    async def fetch_db_messages(self, username: str, receiver: str) -> list:
        async with self.db_pool.acquire() as conn:
            logger.info(f"Fetching messages from DB for {username}/{receiver}")
            messages = await conn.fetch("""
                SELECT id, sender_username, content, timestamp, edited, deleted, reaction, reply_to_id, type
                FROM messages 
                WHERE (sender_username = $1 AND receiver_username = $2) 
                   OR (sender_username = $2 AND receiver_username = $1)
                ORDER BY timestamp ASC
            """, username, receiver)
            logger.info(f"Fetched {len(messages)} messages from DB")
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
        logger.info(f"Updating cache for {cache_key} with {len(messages)} messages")
        await self.redis.set(cache_key, json.dumps(messages), ex=3600)

# WebSocket Manager
class WebSocketManager:
    @staticmethod
    async def broadcast_message(receiver: str, message: dict):
        if receiver in active_connections:
            logger.info(f"Broadcasting message to {receiver}")
            await active_connections[receiver].send_json(message)

    @staticmethod
    async def cleanup_connection(username: str):
        if username in active_connections:
            logger.info(f"Cleaning up connection for {username}")
            del active_connections[username]

# Action Handlers
async def handle_send(handler: MessageHandler, websocket: WebSocket, username: str, receiver: str, data: dict):
    content = data.get("content")
    reply_to_id = data.get("reply_to_id")
    logger.info(f"Handling send action from {username} to {receiver}")
    
    if not content:
        logger.warning("Content is missing in send action")
        await websocket.send_json({"error": "Content is required"})
        return

    async with handler.db_pool.acquire() as conn:
        msg_id = await conn.fetchval(
            "INSERT INTO messages (sender_username, receiver_username, content, reply_to_id, type) "
            "VALUES ($1, $2, $3, $4, 'text') RETURNING id",
            username, receiver, content, reply_to_id
        )
        logger.info(f"Inserted message with ID {msg_id}")
        
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
    
    for user, other in [(username, receiver), (receiver, username)]:
        cache_key = f"messages:{user}:{other}"
        cached = await handler.get_cached_messages(cache_key)
        messages = cached or []
        messages.append(msg)
        await handler.update_cache(cache_key, messages)
    
    await WebSocketManager.broadcast_message(receiver, msg)
    await websocket.send_json(msg)

async def handle_edit(handler: MessageHandler, websocket: WebSocket, username: str, receiver: str, data: dict):
    msg_id = data.get("msg_id")
    new_content = data.get("content")
    logger.info(f"Handling edit action for msg_id {msg_id}")
    
    if not msg_id or not new_content:
        logger.warning("msg_id or content missing in edit action")
        await websocket.send_json({"error": "msg_id and content are required"})
        return
    
    async with handler.db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET content = $1, edited = TRUE WHERE id = $2",
            new_content, msg_id
        )
        logger.info(f"Message {msg_id} edited")
    
    msg = {"action": "edit", "msg_id": msg_id, "content": new_content, "edited": True}
    for user, other in [(username, receiver), (receiver, username)]:
        cache_key = f"messages:{user}:{other}"
        cached = await handler.get_cached_messages(cache_key)
        if cached:
            for m in cached:
                if m["msg_id"] == msg_id:
                    m["content"] = new_content
                    m["edited"] = True
            await handler.update_cache(cache_key, cached)
    
    await WebSocketManager.broadcast_message(receiver, msg)
    await websocket.send_json(msg)

async def handle_delete(handler: MessageHandler, websocket: WebSocket, username: str, receiver: str, data: dict):
    msg_id = data.get("msg_id")
    delete_for_all = data.get("delete_for_all", False)
    logger.info(f"Handling delete action for msg_id {msg_id}, delete_for_all={delete_for_all}")
    
    if not msg_id:
        logger.warning("msg_id missing in delete action")
        await websocket.send_json({"error": "msg_id is required"})
        return
    
    async with handler.db_pool.acquire() as conn:
        await conn.execute("UPDATE messages SET deleted = TRUE WHERE id = $1", msg_id)
        logger.info(f"Message {msg_id} marked as deleted")
    
    msg = {"action": "delete", "msg_id": msg_id, "delete_for_all": delete_for_all, "content": "This message was deleted"}
    for user, other in [(username, receiver), (receiver, username)]:
        cache_key = f"messages:{user}:{other}"
        cached = await handler.get_cached_messages(cache_key)
        if cached:
            for m in cached:
                if m["msg_id"] == msg_id:
                    m["deleted"] = True
                    m["content"] = "This message was deleted"
            await handler.update_cache(cache_key, cached)
    
    await WebSocketManager.broadcast_message(receiver, msg)
    await websocket.send_json(msg)

async def handle_fetch(handler: MessageHandler, websocket: WebSocket, username: str, receiver: str, data: dict):
    logger.info(f"Handling fetch action for {username}/{receiver}")
    cache_key = f"messages:{username}:{receiver}"
    messages = await handler.get_cached_messages(cache_key)
    if not messages:
        messages = await handler.fetch_db_messages(username, receiver)
        await handler.update_cache(cache_key, messages)
    
    for msg in messages:
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
    username = username.replace("%20", " ").strip()
    receiver = receiver.replace("%20", " ").strip()
    logger.info(f"WebSocket connection attempt: {username}/{receiver}")

    # Check if username exists in DB (basic authentication)
    async with db_pool.acquire() as conn:
        user_exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE username = $1)", username)
        if not user_exists:
            logger.warning(f"User {username} not found in database")
            await websocket.close(code=1008, reason="Unauthorized: User not found")
            return

    # Prevent duplicate connections
    if username in active_connections:
        logger.warning(f"Duplicate connection attempt by {username}")
        await websocket.close(code=1000, reason="Duplicate connection")
        return

    await websocket.accept()
    active_connections[username] = websocket
    logger.info(f"{username} connected successfully")

    handler = MessageHandler(db_pool, redis)
    
    # Initial message load
    cache_key = f"messages:{username}:{receiver}"
    messages = await handler.get_cached_messages(cache_key)
    if not messages:
        messages = await handler.fetch_db_messages(username, receiver)
        await handler.update_cache(cache_key, messages)
    logger.info(f"Sending {len(messages)} initial messages to {username}")
    for msg in messages:
        await websocket.send_json(msg)

    # Action dispatcher
    action_handlers = {
        "send": handle_send,
        "edit": handle_edit,
        "delete": handle_delete,
        "fetch": handle_fetch,
    }

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received data from {username}: {data}")
            msg_data = json.loads(data)
            action = msg_data.get("action", "send")
            
            handler_func = action_handlers.get(action)
            if handler_func:
                await handler_func(handler, websocket, username, receiver, msg_data)
            else:
                logger.warning(f"Unknown action received: {action}")
                await websocket.send_json({"error": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        logger.info(f"{username} disconnected")
        await WebSocketManager.cleanup_connection(username)
    except Exception as e:
        logger.error(f"Error occurred for {username}: {str(e)}", exc_info=True)
        await WebSocketManager.cleanup_connection(username)
        await websocket.close(code=1011, reason=f"Internal server error: {str(e)}")