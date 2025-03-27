from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from config import app, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from models import UserRegister, UserLogin, PasswordReset, VerifyResetCode, NewPassword
import psycopg2
from fastapi.responses import JSONResponse
import os
import random
from database import get_db
from utils import hash_password, send_reset_code
import json
from datetime import datetime
import cloudinary
import cloudinary.uploader


router = APIRouter()

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Foydalanuvchilarni saqlash (WebSocket uchun)
active_connections = {} 










@router.websocket("/ws/{username}/{receiver}")
async def websocket_endpoint(websocket: WebSocket, username: str, receiver: str):
    await websocket.accept()
    username = username.replace("%20", " ").strip()
    receiver = receiver.replace("%20", " ").strip()
    active_connections[username] = websocket

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
        for msg in messages:
            await websocket.send_json({
                "msg_id": msg["id"],
                "sender": msg["sender_username"],
                "content": msg["content"] if not msg["deleted"] else "This message was deleted",
                "timestamp": msg["timestamp"].isoformat(),
                "edited": msg["edited"],
                "deleted": msg["deleted"],
                "reaction": msg["reaction"] if msg["reaction"] else None,
                "reply_to_id": msg["reply_to_id"] if msg["reply_to_id"] else None
            })

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            action = msg_data.get("action", "send")

            with get_db() as conn:
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
                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)

    except WebSocketDisconnect:
        if username in active_connections:
            del active_connections[username]
        print(f"{username} uzildi")














# Register endpoint
@router.post("/register")
async def register(user: UserRegister):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        hashed_password = hash_password(user.password)
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (user.username, user.email, hashed_password)
            )
            conn.commit()
            return {"message": "Foydalanuvchi muvaffaqiyatli ro‘yxatdan o‘tdi"}
        except psycopg2.IntegrityError:
            raise HTTPException(status_code=400, detail="Username yoki email allaqachon mavjud")

# Login endpoint
@router.post("/login")
async def login(user: UserLogin):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        hashed_password = hash_password(user.password)
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s",
            (user.username, hashed_password)
        )
        result = cursor.fetchone()
        if result:
            return {"message": "Kirish muvaffaqiyatli", "username": result["username"]}
        raise HTTPException(status_code=401, detail="Username yoki parol noto‘g‘ri")

# Parolni tiklash uchun kod yuborish
@router.post("/reset-password")
async def reset_password(data: PasswordReset):
    reset_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("UPDATE users SET reset_code = %s WHERE email = %s", (reset_code, data.email))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email topilmadi")
        conn.commit()

    send_reset_code(data.email, reset_code)
    return {"message": "Tiklash kodi emailingizga yuborildi"}

# Reset kodni tekshirish
@router.post("/verify-reset-code")
async def verify_reset_code(data: VerifyResetCode):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND reset_code = %s",
            (data.email, data.reset_code)
        )
        result = cursor.fetchone()
        if result:
            return {"message": "Kod to‘g‘ri"}
        raise HTTPException(status_code=400, detail="Kod noto‘g‘ri yoki email topilmadi")

# Yangi parolni o‘rnatish
@router.post("/set-new-password")
async def set_new_password(data: NewPassword):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        hashed_password = hash_password(data.new_password)
        cursor.execute(
            "UPDATE users SET password = %s, reset_code = NULL WHERE email = %s",
            (hashed_password, data.email)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email topilmadi")
        conn.commit()
        return {"message": "Yangi parol muvaffaqiyatli o‘rnatildi"}

# Userlarni izlash
@router.get("/users")
async def get_users(query: str = ""):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT username FROM users WHERE username ILIKE %s", (f"%{query}%",))
        users = cursor.fetchall()
        return [{"username": user["username"]} for user in users]
    

# ... boshqa importlar ...

@router.post("/upload")
async def upload_file(file: UploadFile, sender: str = Form(...), receiver: str = Form(...)):
    try:
        # Cloudinary’ga faylni yuklash
        upload_result = cloudinary.uploader.upload(file.file, 
            folder="chatapp_media",  # Cloudinary’da papka nomi
            resource_type="auto"     # Rasm yoki video ekanligini avto aniqlash
        )
        file_url = upload_result["secure_url"]  # Xavfsiz HTTPS URL
        print(f"Uploaded to Cloudinary: {file_url}")  # Log uchun
        return {"file_url": file_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary yuklash xatosi: {str(e)}")

app.include_router(router)