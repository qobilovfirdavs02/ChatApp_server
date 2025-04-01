from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
from datetime import datetime
from database import get_db, get_redis
from redis.asyncio import Redis  # Yangi import
import psycopg2.extras

router = APIRouter()
active_connections = {}

@router.websocket("/ws/{username}/{receiver}")
async def websocket_endpoint(websocket: WebSocket, username: str, receiver: str, redis: Redis = Depends(get_redis)):
    await websocket.accept()
    username = username.replace("%20", " ").strip()
    receiver = receiver.replace("%20", " ").strip()
    active_connections[username] = websocket

    # Redis’dan keshlangan xabarlarni olish
    cache_key = f"messages:{username}:{receiver}"
    cached_messages = await redis.get(cache_key)
    if cached_messages:
        messages = json.loads(cached_messages)
        for msg in messages:
            await websocket.send_json(msg)
    else:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""
                SELECT id, sender_username, content, timestamp, edited, deleted, reaction, reply_to_id 
                FROM messages 
                WHERE (sender_username = %s AND receiver_username = %s) 
                   OR (sender_username = %s AND receiver_username = %s)
                ORDER BY timestamp ASC
            """, (username, receiver, receiver, username))
            messages = cursor.fetchall()
            msg_list = [
                {
                    "msg_id": msg["id"],
                    "sender": msg["sender_username"],
                    "content": msg["content"] if not msg["deleted"] else "This message was deleted",
                    "timestamp": msg["timestamp"].isoformat(),
                    "edited": msg["edited"],
                    "deleted": msg["deleted"],
                    "reaction": msg["reaction"] if msg["reaction"] else None,
                    "reply_to_id": msg["reply_to_id"] if msg["reply_to_id"] else None
                } for msg in messages
            ]
            await redis.set(cache_key, json.dumps(msg_list), ex=3600)  # ex TTL uchun
            for msg in msg_list:
                await websocket.send_json(msg)

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            action = msg_data.get("action", "send")

            with db as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                if action == "send":
                    content = msg_data.get("content")
                    reply_to_id = msg_data.get("reply_to_id")
                    if not content:
                        await websocket.send_json({"error": "Content is required for send action"})
                        continue
                    cursor.execute(
                        "INSERT INTO messages (sender_username, receiver_username, content, reply_to_id) VALUES (%s, %s, %s, %s) RETURNING id",
                        (username, receiver, content, reply_to_id)
                    )
                    msg_id = cursor.fetchone()["id"]
                    conn.commit()
                    msg = {
                        "msg_id": msg_id,
                        "sender": username,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                        "edited": False,
                        "deleted": False,
                        "reaction": None,
                        "reply_to_id": reply_to_id if reply_to_id else None
                    }
                    # Keshni yangilash
                    cached_messages = await redis.get(cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        msg_list.append(msg)
                        await redis.set(cache_key, json.dumps(msg_list), expire=3600)
                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

                elif action == "edit":
                    msg_id = msg_data.get("msg_id")
                    new_content = msg_data.get("content")
                    if not msg_id or not new_content:
                        await websocket.send_json({"error": "msg_id and content are required for edit action"})
                        continue
                    cursor.execute(
                        "UPDATE messages SET content = %s, edited = %s WHERE id = %s",
                        (new_content, True, msg_id)
                    )
                    conn.commit()
                    msg = {
                        "action": "edit",
                        "msg_id": msg_id,
                        "content": new_content,
                        "edited": True
                    }
                    # Keshni yangilash
                    cached_messages = await redis.get(cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id:
                                m["content"] = new_content
                                m["edited"] = True
                        await redis.set(cache_key, json.dumps(msg_list), expire=3600)
                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

                elif action == "delete":
                    msg_id = msg_data.get("msg_id")
                    delete_for_all = msg_data.get("delete_for_all", False)
                    if not msg_id:
                        await websocket.send_json({"error": "msg_id is required for delete action"})
                        continue
                    if delete_for_all:
                        cursor.execute(
                            "UPDATE messages SET deleted = %s WHERE id = %s",
                            (True, msg_id)
                        )
                    conn.commit()
                    msg = {
                        "action": "delete",
                        "msg_id": msg_id,
                        "delete_for_all": delete_for_all,
                        "content": "This message was deleted" if delete_for_all else None
                    }
                    # Keshni yangilash
                    cached_messages = await redis.get(cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id and delete_for_all:
                                m["content"] = "This message was deleted"
                                m["deleted"] = True
                        await redis.set(cache_key, json.dumps(msg_list), expire=3600)
                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

                elif action == "delete_permanent":
                    msg_id = msg_data.get("msg_id")
                    if not msg_id:
                        await websocket.send_json({"error": "msg_id is required for delete_permanent action"})
                        continue
                    cursor.execute(
                        "DELETE FROM messages WHERE id = %s",
                        (msg_id,)
                    )
                    conn.commit()
                    msg = {
                        "action": "delete_permanent",
                        "msg_id": msg_id
                    }
                    # Keshni yangilash
                    cached_messages = await redis.get(cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        msg_list = [m for m in msg_list if m["msg_id"] != msg_id]
                        await redis.set(cache_key, json.dumps(msg_list), expire=3600)
                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

    except WebSocketDisconnect:
        if username in active_connections:
            del active_connections[username]
        print(f"{username} uzildi")