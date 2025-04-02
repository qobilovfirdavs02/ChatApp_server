from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
from datetime import datetime
from database import get_db, get_redis
from redis.asyncio import Redis
import psycopg2.extras
import logging




router = APIRouter()
active_connections = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.websocket("/ws/{username}/{receiver}")
async def websocket_endpoint(websocket: WebSocket, username: str, receiver: str, db=Depends(get_db), redis: Redis = Depends(get_redis)):
    await websocket.accept()
    logger.info(f"{username} ulandi")

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
        with db as conn:
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
                    "reply_to_id": msg["reply_to_id"] if msg["reply_to_id"] else None,
                    "type": "text" # Yangi qo‘shildi
                } for msg in messages
            ]
            await redis.set(cache_key, json.dumps(msg_list), ex=3600)
            for msg in msg_list:
                await websocket.send_json(msg)

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Qabul qilingan ma'lumot: {data}")
            msg_data = json.loads(data)
            action = msg_data.get("action", "send")
            logger.info(f"Action: {action}")

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
                        "reply_to_id": reply_to_id if reply_to_id else None,
                        "type": "text" # Yangi qo‘shildi
                    }
                    sender_cache_key = f"messages:{username}:{receiver}"
                    cached_messages = await redis.get(sender_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        msg_list.append(msg)
                        await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)
                    else:
                        await redis.set(sender_cache_key, json.dumps([msg]), ex=3600)

                    receiver_cache_key = f"messages:{receiver}:{username}"
                    cached_messages = await redis.get(receiver_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        msg_list.append(msg)
                        await redis.set(receiver_cache_key, json.dumps(msg_list), ex=3600)
                    else:
                        await redis.set(receiver_cache_key, json.dumps([msg]), ex=3600)

                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

                elif action == "edit":
                    msg_id = msg_data.get("msg_id")
                    new_content = msg_data.get("content")
                    if not msg_id or not new_content:
                        await websocket.send_json({"error": "msg_id and content are required"})
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
                    sender_cache_key = f"messages:{username}:{receiver}"
                    cached_messages = await redis.get(sender_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id:
                                m["content"] = new_content
                                m["edited"] = True
                        await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)

                    receiver_cache_key = f"messages:{receiver}:{username}"
                    cached_messages = await redis.get(receiver_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id:
                                m["content"] = new_content
                                m["edited"] = True
                        await redis.set(receiver_cache_key, json.dumps(msg_list), ex=3600)

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
                    sender_cache_key = f"messages:{username}:{receiver}"
                    cached_messages = await redis.get(sender_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id and delete_for_all:
                                m["content"] = "This message was deleted"
                                m["deleted"] = True
                        await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)

                    receiver_cache_key = f"messages:{receiver}:{username}"
                    cached_messages = await redis.get(receiver_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id and delete_for_all:
                                m["content"] = "This message was deleted"
                                m["deleted"] = True
                        await redis.set(receiver_cache_key, json.dumps(msg_list), ex=3600)

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
                    sender_cache_key = f"messages:{username}:{receiver}"
                    cached_messages = await redis.get(sender_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        msg_list = [m for m in msg_list if m["msg_id"] != msg_id]
                        await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)

                    receiver_cache_key = f"messages:{receiver}:{username}"
                    cached_messages = await redis.get(receiver_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        msg_list = [m for m in msg_list if m["msg_id"] != msg_id]
                        await redis.set(receiver_cache_key, json.dumps(msg_list), ex=3600)

                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

                elif action == "react":
                    msg_id = msg_data.get("msg_id")
                    reaction = msg_data.get("reaction")
                    if not msg_id or not reaction:
                        await websocket.send_json({"error": "msg_id and reaction are required"})
                        continue
                    cursor.execute(
                        "UPDATE messages SET reaction = %s WHERE id = %s",
                        (reaction, msg_id)
                    )
                    conn.commit()
                    msg = {
                        "action": "react",
                        "msg_id": msg_id,
                        "reaction": reaction
                    }
                    sender_cache_key = f"messages:{username}:{receiver}"
                    cached_messages = await redis.get(sender_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id:
                                m["reaction"] = reaction
                        await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)

                    receiver_cache_key = f"messages:{receiver}:{username}"
                    cached_messages = await redis.get(receiver_cache_key)
                    if cached_messages:
                        msg_list = json.loads(cached_messages)
                        for m in msg_list:
                            if m["msg_id"] == msg_id:
                                m["reaction"] = reaction
                        await redis.set(receiver_cache_key, json.dumps(msg_list), ex=3600)

                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

                elif action == "fetch":
                    sender_cache_key = f"messages:{username}:{receiver}"
                    logger.info(f"Fetch boshlandi: {username} -> {receiver}")
                    cached_messages = await redis.get(sender_cache_key)
                    if cached_messages:
                        messages = json.loads(cached_messages)
                        logger.info(f"Redis’dan {len(messages)} ta xabar olindi")
                        for msg in messages:
                            await websocket.send_json(msg)
                    else:
                        cursor.execute("""
                            SELECT id, sender_username, content, timestamp, edited, deleted, reaction, reply_to_id 
                            FROM messages 
                            WHERE (sender_username = %s AND receiver_username = %s) 
                               OR (sender_username = %s AND receiver_username = %s)
                            ORDER BY timestamp ASC
                        """, (username, receiver, receiver, username))
                        messages = cursor.fetchall()
                        logger.info(f"DB’dan {len(messages)} ta xabar olindi")
                        msg_list = [
                            {
                                "msg_id": msg["id"],
                                "sender": msg["sender_username"],
                                "content": msg["content"] if not msg["deleted"] else "This message was deleted",
                                "timestamp": msg["timestamp"].isoformat(),
                                "edited": msg["edited"],
                                "deleted": msg["deleted"],
                                "reaction": msg["reaction"] if msg["reaction"] else None,
                                "reply_to_id": msg["reply_to_id"] if msg["reply_to_id"] else None,
                                "type": "text"  # Yangi qo‘shildi
                            } for msg in messages
                        ]
                        await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)
                        for msg in msg_list:
                            await websocket.send_json(msg)
                    
                




                # elif action == "voice":
                #     file_url = msg_data.get("file_url")
                #     logger.info(f"Voice action qabul qilindi: {msg_data}")
                #     msg_id = msg_data.get("msg_id", None)
                #     if not file_url or not msg_id:
                #         logger.error(f"Xato: file_url={file_url}, msg_id={msg_id}")
                #         await websocket.send_json({"error": "file_url and msg_id are required for voice action"})
                #         continue
                #     cursor.execute(
                #         "INSERT INTO messages (sender_username, receiver_username, content, type) VALUES (%s, %s, %s, %s) RETURNING id",
                #         (username, receiver, file_url, "voice")
                #     )
                #     new_msg_id = cursor.fetchone()["id"]
                #     conn.commit()
                #     msg = {
                #         "msg_id": new_msg_id,
                #         "sender": username,
                #         "content": file_url,
                #         "timestamp": datetime.now().isoformat(),
                #         "type": "voice",
                #         "action": "voice"
                #     }
                #     sender_cache_key = f"messages:{username}:{receiver}"
                #     cached_messages = await redis.get(sender_cache_key)
                #     if cached_messages:
                #         msg_list = json.loads(cached_messages)
                #         msg_list.append(msg)
                #         await redis.set(sender_cache_key, json.dumps(msg_list), ex=3600)
                #     else:
                #         await redis.set(sender_cache_key, json.dumps([msg]), ex=3600)

                #     receiver_cache_key = f"messages:{receiver}:{username}"
                #     cached_messages = await redis.get(receiver_cache_key)
                #     if cached_messages:
                #         msg_list = json.loads(cached_messages)
                #         msg_list.append(msg)
                #         await redis.set(receiver_cache_key, json.dumps(msg_list), ex=3600)
                #     else:
                #         await redis.set(receiver_cache_key, json.dumps([msg]), ex=3600)

                #     if receiver in active_connections:
                #         await active_connections[receiver].send_json(msg)
                #     await websocket.send_json(msg)








    except WebSocketDisconnect:
        logger.info(f"{username} uzildi (WebSocketDisconnect)")
        if username in active_connections:
            del active_connections[username]
    except Exception as e:
        logger.error(f"xato yuz berdi: {str(e)}")
        if username in active_connections:
            del active_connections[username]
        
 
        














        