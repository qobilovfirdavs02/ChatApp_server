from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
from datetime import datetime
from database import get_db, get_redis
from redis.asyncio import Redis
import psycopg2.extras
import logging
from typing import Dict, List, Optional

router = APIRouter()
active_connections: Dict[str, WebSocket] = {}
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Yordamchi funksiyalar
def clean_param(param: str) -> str:
    """Parametrlarni tozalash."""
    return param.replace("%20", " ").strip()

def format_message(msg: dict, deleted_content: str = "This message was deleted") -> dict:
    """Xabarni formatlash."""
    return {
        "msg_id": msg["id"],
        "sender": msg["sender_username"],
        "content": deleted_content if msg["deleted"] else msg["content"],
        "timestamp": msg["timestamp"].isoformat(),
        "edited": msg["edited"],
        "deleted": msg["deleted"],
        "reaction": msg["reaction"] or None,
        "reply_to_id": msg["reply_to_id"] or None,
        "type": msg.get("type", "text")
    }

async def fetch_messages(cursor, username: str, receiver: str) -> List[dict]:
    """DB’dan xabarlarni olish."""
    await cursor.execute("""
        SELECT id, sender_username, content, timestamp, edited, deleted, reaction, reply_to_id, type
        FROM messages 
        WHERE (sender_username = %s AND receiver_username = %s) 
           OR (sender_username = %s AND receiver_username = %s)
        ORDER BY timestamp ASC
    """, (username, receiver, receiver, username))
    return [format_message(msg) for msg in await cursor.fetchall()]

async def update_cache(redis: Redis, sender_key: str, receiver_key: str, msg: dict, action: str = "send") -> None:
    """Redis keshini yangilash."""
    keys = [sender_key, receiver_key]
    for key in keys:
        cached = await redis.get(key)
        msg_list = json.loads(cached) if cached else []
        
        if action in ("send", "voice"):
            msg_list.append(msg)
        elif action == "edit":
            for m in msg_list:
                if m["msg_id"] == msg["msg_id"]:
                    m.update({"content": msg["content"], "edited": True})
        elif action == "delete" and msg.get("delete_for_all"):
            for m in msg_list:
                if m["msg_id"] == msg["msg_id"]:
                    m.update({"content": "This message was deleted", "deleted": True})
        elif action == "delete_permanent":
            msg_list = [m for m in msg_list if m["msg_id"] != msg["msg_id"]]
        elif action == "react":
            for m in msg_list:
                if m["msg_id"] == msg["msg_id"]:
                    m["reaction"] = msg["reaction"]
        
        await redis.setex(key, 3600, json.dumps(msg_list))

@router.websocket("/ws/{username}/{receiver}")
async def websocket_endpoint(websocket: WebSocket, username: str, receiver: str, 
                            db=Depends(get_db), redis: Redis = Depends(get_redis)):
    await websocket.accept()
    
    # Parametrlarni tozalash va ulanishni saqlash
    username = clean_param(username)
    receiver = clean_param(receiver)
    active_connections[username] = websocket
    logger.info(f"{username} ulandi")

    # Redis’dan keshlangan xabarlarni olish
    cache_key = f"messages:{username}:{receiver}"
    cached_messages = await redis.get(cache_key)
    if cached_messages:
        await websocket.send_json({"action": "bulk", "messages": json.loads(cached_messages)})
    else:
        async with db as conn:
            async with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                msg_list = await fetch_messages(cursor, username, receiver)
                await redis.setex(cache_key, 3600, json.dumps(msg_list))
                await websocket.send_json({"action": "bulk", "messages": msg_list})

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            action = msg_data.get("action", "send")
            logger.info(f"Action: {action}")

            async with db as conn:
                async with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    sender_key = f"messages:{username}:{receiver}"
                    receiver_key = f"messages:{receiver}:{username}"

                    if action == "send":
                        content = msg_data.get("content")
                        reply_to_id = msg_data.get("reply_to_id")
                        if not content:
                            await websocket.send_json({"error": "Content is required"})
                            continue
                        await cursor.execute(
                            "INSERT INTO messages (sender_username, receiver_username, content, reply_to_id) VALUES (%s, %s, %s, %s) RETURNING id",
                            (username, receiver, content, reply_to_id)
                        )
                        msg_id = (await cursor.fetchone())["id"]
                        await conn.commit()
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
                        await update_cache(redis, sender_key, receiver_key, msg)
                        if receiver in active_connections:
                            await active_connections[receiver].send_json(msg)
                        await websocket.send_json(msg)

                    elif action == "edit":
                        msg_id = msg_data.get("msg_id")
                        content = msg_data.get("content")
                        if not (msg_id and content):
                            await websocket.send_json({"error": "msg_id and content are required"})
                            continue
                        await cursor.execute(
                            "UPDATE messages SET content = %s, edited = true WHERE id = %s",
                            (content, msg_id)
                        )
                        await conn.commit()
                        msg = {"action": "edit", "msg_id": msg_id, "content": content, "edited": True}
                        await update_cache(redis, sender_key, receiver_key, msg, "edit")
                        if receiver in active_connections:
                            await active_connections[receiver].send_json(msg)
                        await websocket.send_json(msg)

                    elif action == "delete":
                        msg_id = msg_data.get("msg_id")
                        delete_for_all = msg_data.get("delete_for_all", False)
                        if not msg_id:
                            await websocket.send_json({"error": "msg_id is required"})
                            continue
                        if delete_for_all:
                            await cursor.execute("UPDATE messages SET deleted = true WHERE id = %s", (msg_id,))
                            await conn.commit()
                        msg = {
                            "action": "delete",
                            "msg_id": msg_id,
                            "delete_for_all": delete_for_all,
                            "content": "This message was deleted" if delete_for_all else None
                        }
                        await update_cache(redis, sender_key, receiver_key, msg, "delete")
                        if receiver in active_connections:
                            await active_connections[receiver].send_json(msg)
                        await websocket.send_json(msg)

                    elif action == "delete_permanent":
                        msg_id = msg_data.get("msg_id")
                        if not msg_id:
                            await websocket.send_json({"error": "msg_id is required"})
                            continue
                        await cursor.execute("DELETE FROM messages WHERE id = %s", (msg_id,))
                        await conn.commit()
                        msg = {"action": "delete_permanent", "msg_id": msg_id}
                        await update_cache(redis, sender_key, receiver_key, msg, "delete_permanent")
                        if receiver in active_connections:
                            await active_connections[receiver].send_json(msg)
                        await websocket.send_json(msg)

                    elif action == "react":
                        msg_id = msg_data.get("msg_id")
                        reaction = msg_data.get("reaction")
                        if not (msg_id and reaction):
                            await websocket.send_json({"error": "msg_id and reaction are required"})
                            continue
                        await cursor.execute("UPDATE messages SET reaction = %s WHERE id = %s", (reaction, msg_id))
                        await conn.commit()
                        msg = {"action": "react", "msg_id": msg_id, "reaction": reaction}
                        await update_cache(redis, sender_key, receiver_key, msg, "react")
                        if receiver in active_connections:
                            await active_connections[receiver].send_json(msg)
                        await websocket.send_json(msg)

                    elif action == "fetch":
                        cached = await redis.get(sender_key)
                        if cached:
                            await websocket.send_json({"action": "bulk", "messages": json.loads(cached)})
                        else:
                            msg_list = await fetch_messages(cursor, username, receiver)
                            await redis.setex(sender_key, 3600, json.dumps(msg_list))
                            await websocket.send_json({"action": "bulk", "messages": msg_list})

                    elif action == "voice":
                        file_url = msg_data.get("file_url")
                        if not file_url:
                            await websocket.send_json({"error": "file_url is required"})
                            continue
                        await cursor.execute(
                            "INSERT INTO messages (sender_username, receiver_username, content, type) VALUES (%s, %s, %s, 'voice') RETURNING id",
                            (username, receiver, file_url)
                        )
                        msg_id = (await cursor.fetchone())["id"]
                        await conn.commit()
                        msg = {
                            "msg_id": msg_id,
                            "sender": username,
                            "content": file_url,
                            "timestamp": datetime.now().isoformat(),
                            "type": "voice",
                            "action": "voice"
                        }
                        await update_cache(redis, sender_key, receiver_key, msg, "voice")
                        if receiver in active_connections:
                            await active_connections[receiver].send_json(msg)
                        await websocket.send_json(msg)

    except WebSocketDisconnect:
        logger.info(f"{username} uzildi")
        active_connections.pop(username, None)
    except Exception as e:
        logger.error(f"Xato: {str(e)}")
        active_connections.pop(username, None)