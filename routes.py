from fastapi import APIRouter, HTTPException, UploadFile, Form, Depends
from fastapi.staticfiles import StaticFiles
from config import app, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from models import UserRegister, UserLogin, PasswordReset, VerifyResetCode, NewPassword
import psycopg2
from fastapi.responses import JSONResponse
import os
import random
from database import get_db
from utils import hash_password, send_reset_code
import cloudinary
import cloudinary.uploader

router = APIRouter()

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Register endpoint
@router.post("/register")
async def register(user: UserRegister, db=Depends(get_db)):
    with db as conn:
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
async def login(user: UserLogin, db=Depends(get_db)):
    with db as conn:
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
async def reset_password(data: PasswordReset, db=Depends(get_db)):
    reset_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    with db as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("UPDATE users SET reset_code = %s WHERE email = %s", (reset_code, data.email))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email topilmadi")
        conn.commit()

    send_reset_code(data.email, reset_code)
    return {"message": "Tiklash kodi emailingizga yuborildi"}

# Reset kodni tekshirish
@router.post("/verify-reset-code")
async def verify_reset_code(data: VerifyResetCode, db=Depends(get_db)):
    with db as conn:
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
async def set_new_password(data: NewPassword, db=Depends(get_db)):
    with db as conn:
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
async def get_users(query: str = "", db=Depends(get_db)):
    with db as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT username FROM users WHERE username ILIKE %s", (f"%{query}%",))
        users = cursor.fetchall()
        return [{"username": user["username"]} for user in users]

# Fayl yuklash
# @router.post("/upload")
# async def upload_file(file: UploadFile, sender: str = Form(...), receiver: str = Form(...)):
#     try:
#         upload_result = cloudinary.uploader.upload(file.file,
#             folder="chatapp_media",
#             resource_type="auto"
#         )
#         file_url = upload_result["secure_url"]
#         print(f"Uploaded to Cloudinary: {file_url}")
#         return {"file_url": file_url}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Cloudinary yuklash xatosi: {str(e)}")

@router.post("/upload")
async def upload_file(file: UploadFile, sender: str = Form(...), receiver: str = Form(...)):
    try:
        upload_result = cloudinary.uploader.upload(file.file,
            folder="chatapp_media",
            resource_type="auto"
        )
        file_url = upload_result["secure_url"]
        print(f"Uploaded to Cloudinary: {file_url}")
        return {"file_url": file_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary yuklash xatosi: {str(e)}")

app.include_router(router)