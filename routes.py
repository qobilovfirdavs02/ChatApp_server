# routes.py
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from config import app
from models import UserRegister, UserLogin, PasswordReset, VerifyResetCode, NewPassword
import psycopg2
import random
from database import get_db
from utils import hash_password, send_reset_code
import json
from datetime import datetime

# Foydalanuvchilarni saqlash (WebSocket uchun)
active_connections = {}  # {username: WebSocket}

# routes.py (faqat WebSocket qismi yangilandi)
# routes.py (faqat WebSocket qismi yangilandi)
@app.websocket("/ws/{username}/{receiver}")
async def websocket_endpoint(websocket: WebSocket, username: str, receiver: str):
    # Ulanishni qabul qilish
    await websocket.accept()
    print(f"WebSocket ulanishi qabul qilindi: {username} -> {receiver}")

    # Username va receiver ni tozalash
    username = username.replace("%20", " ").strip()
    receiver = receiver.replace("%20", " ").strip()
    active_connections[username] = websocket
    print(f"Ulanish ochildi: {username} -> {receiver}")
    print(f"Active connections: {active_connections.keys()}")

    # Tarixdagi xabarlarni yuborish
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sender_username, content, timestamp, edited, deleted 
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
                    "edited": msg["edited"]
                })

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            content = msg_data["content"]
            action = msg_data.get("action", "send")
            print(f"Xabar keldi: {username} -> {receiver}, content: {content}")

            with get_db() as conn:
                cursor = conn.cursor()
                if action == "send":
                    cursor.execute(
                        "INSERT INTO messages (sender_username, receiver_username, content) VALUES (%s, %s, %s) RETURNING id",
                        (username, receiver, content)
                    )
                    msg_id = cursor.fetchone()["id"]
                    conn.commit()
                    msg = {
                        "msg_id": msg_id,
                        "sender": username,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                        "edited": False
                    }
                    if receiver in active_connections:
                        await active_connections[receiver].send_json(msg)
                    await websocket.send_json(msg)
                elif action == "edit":
                    msg_id = msg_data["msg_id"]
                    cursor.execute(
                        "SELECT timestamp FROM messages WHERE id = %s AND sender_username = %s",
                        (msg_id, username)
                    )
                    result = cursor.fetchone()
                    if result:
                        sent_time = result["timestamp"]
                        if (datetime.now() - sent_time).total_seconds() <= 1800:  # 30 daqiqa
                            cursor.execute(
                                "UPDATE messages SET content = %s, edited = TRUE WHERE id = %s AND sender_username = %s",
                                (content, msg_id, username)
                            )
                            conn.commit()
                            msg = {
                                "msg_id": msg_id,
                                "sender": username,
                                "content": content,
                                "timestamp": sent_time.isoformat(),
                                "edited": True
                            }
                            if receiver in active_connections:
                                await active_connections[receiver].send_json(msg)
                            await websocket.send_json(msg)
                        else:
                            await websocket.send_json({"error": "30 daqiqa o‘tdi"})
                    else:
                        await websocket.send_json({"error": "Xabar topilmadi"})
                elif action == "delete":
                    msg_id = msg_data["msg_id"]
                    cursor.execute(
                        "UPDATE messages SET deleted = TRUE WHERE id = %s AND sender_username = %s",
                        (msg_id, username)
                    )
                    conn.commit()

    except WebSocketDisconnect:
        if username in active_connections:
            del active_connections[username]
        print(f"{username} uzildi")



# Register endpoint
@app.post("/register")
async def register(user: UserRegister):
    with get_db() as conn:
        cursor = conn.cursor()
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
@app.post("/login")
async def login(user: UserLogin):
    with get_db() as conn:
        cursor = conn.cursor()
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
@app.post("/reset-password")
async def reset_password(data: PasswordReset):
    reset_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET reset_code = %s WHERE email = %s", (reset_code, data.email))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email topilmadi")
        conn.commit()

    send_reset_code(data.email, reset_code)
    return {"message": "Tiklash kodi emailingizga yuborildi"}

# Reset kodni tekshirish
@app.post("/verify-reset-code")
async def verify_reset_code(data: VerifyResetCode):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND reset_code = %s",
            (data.email, data.reset_code)
        )
        result = cursor.fetchone()
        if result:
            return {"message": "Kod to‘g‘ri"}
        raise HTTPException(status_code=400, detail="Kod noto‘g‘ri yoki email topilmadi")

# Yangi parolni o‘rnatish
@app.post("/set-new-password")
async def set_new_password(data: NewPassword):
    with get_db() as conn:
        cursor = conn.cursor()
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
@app.get("/users")
async def get_users(query: str = ""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username ILIKE %s", (f"%{query}%",))
        users = cursor.fetchall()
        return [{"username": user["username"]} for user in users]