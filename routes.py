from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from config import app
from models import UserRegister, UserLogin, PasswordReset, VerifyResetCode, NewPassword
import psycopg2
from fastapi.responses import JSONResponse
import os
import random
from database import get_db
from utils import hash_password, send_reset_code
import json
from datetime import datetime

router = APIRouter()
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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
            if not msg["deleted"]:
                await websocket.send_json({
                    "msg_id": msg["id"],
                    "sender": msg["sender_username"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"].isoformat(),
                    "edited": msg["edited"],
                    "reaction": msg["reaction"] if msg["reaction"] else None,  
                    "reply_to_id": msg["reply_to_id"] if msg["reply_to_id"] else None  
                })

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            content = msg_data["content"]
            action = msg_data.get("action", "send")

            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                if action == "send":
                    reply_to_id = msg_data.get("reply_to_id")
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
                        "reaction": None,
                        "reply_to_id": reply_to_id if reply_to_id else None
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
    

@router.post("/upload")
async def upload_file(file: UploadFile, sender: str = Form(...), receiver: str = Form(...)):
    try:
        os.makedirs("uploads", exist_ok=True)
        file_location = f"uploads/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())
        file_url = f"https://web-production-545c.up.railway.app/{file_location}"
        return {"file_url": file_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fayl yuklash xatosi: {str(e)}")

app.include_router(router)