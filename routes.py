# from fastapi import APIRouter, HTTPException, UploadFile, Form, Depends
# from fastapi.staticfiles import StaticFiles
# from config import app, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
# from models import UserRegister, UserLogin, PasswordReset, VerifyResetCode, NewPassword
# import psycopg2
# from fastapi.responses import JSONResponse
# import os
# import random
# from database import get_db
# from utils import hash_password, send_reset_code
# import cloudinary
# import cloudinary.uploader
# import logging

# router = APIRouter()
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# cloudinary.config(
#     cloud_name=CLOUDINARY_CLOUD_NAME,
#     api_key=CLOUDINARY_API_KEY,
#     api_secret=CLOUDINARY_API_SECRET
# )


# @router.post("/register")
# async def register(user: UserRegister, db=Depends(get_db)):
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         hashed_password = hash_password(user.password)
#         try:
#             cursor.execute(
#                 "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
#                 (user.username, user.email, hashed_password)
#             )
#             conn.commit()
#             return {"message": "Foydalanuvchi muvaffaqiyatli ro‘yxatdan o‘tdi"}
#         except psycopg2.IntegrityError:
#             raise HTTPException(status_code=400, detail="Username yoki email allaqachon mavjud")


# @router.post("/login")
# async def login(user: UserLogin, db=Depends(get_db)):
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         hashed_password = hash_password(user.password)
#         cursor.execute(
#             "SELECT * FROM users WHERE username = %s AND password = %s",
#             (user.username, hashed_password)
#         )
#         result = cursor.fetchone()
#         if result:
#             return {"message": "Kirish muvaffaqiyatli", "username": result["username"]}
#         raise HTTPException(status_code=401, detail="Username yoki parol noto‘g‘ri")


# @router.post("/reset-password")
# async def reset_password(data: PasswordReset, db=Depends(get_db)):
#     reset_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         cursor.execute("UPDATE users SET reset_code = %s WHERE email = %s", (reset_code, data.email))
#         if cursor.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Email topilmadi")
#         conn.commit()

#     send_reset_code(data.email, reset_code)
#     return {"message": "Tiklash kodi emailingizga yuborildi"}


# @router.post("/verify-reset-code")
# async def verify_reset_code(data: VerifyResetCode, db=Depends(get_db)):
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         cursor.execute(
#             "SELECT * FROM users WHERE email = %s AND reset_code = %s",
#             (data.email, data.reset_code)
#         )
#         result = cursor.fetchone()
#         if result:
#             return {"message": "Kod to‘g‘ri"}
#         raise HTTPException(status_code=400, detail="Kod noto‘g‘ri yoki email topilmadi")


# @router.post("/set-new-password")
# async def set_new_password(data: NewPassword, db=Depends(get_db)):
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         hashed_password = hash_password(data.new_password)
#         cursor.execute(
#             "UPDATE users SET password = %s, reset_code = NULL WHERE email = %s",
#             (hashed_password, data.email)
#         )
#         if cursor.rowcount == 0:
#             raise HTTPException(status_code=404, detail="Email topilmadi")
#         conn.commit()
#         return {"message": "Yangi parol muvaffaqiyatli o‘rnatildi"}


# @router.get("/users")
# async def get_users(query: str = "", db=Depends(get_db)):
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         cursor.execute("SELECT username FROM users WHERE username ILIKE %s", (f"%{query}%",))
#         users = cursor.fetchall()
#         return [{"username": user["username"]} for user in users]

# @router.post("/upload")
# async def upload_file(file: UploadFile, sender: str = Form(...), receiver: str = Form(...)):
#     logger.info(f"Upload so‘rovi: sender={sender}, receiver={receiver}, file={file.filename}")
#     try:
#         upload_result = cloudinary.uploader.upload(file.file,
#             folder="chatapp_media",
#             resource_type="auto"  # Cloudinary fayl turini avtomatik aniqlaydi (.ogg qoladi)
#         )
#         file_url = upload_result["secure_url"]
#         logger.info(f"Uploaded to Cloudinary: {file_url}")
#         return {"file_url": file_url}
#     except Exception as e:
#         logger.error(f"Cloudinary yuklash xatosi: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Cloudinary yuklash xatosi: {str(e)}")

# app.include_router(router)


from fastapi import APIRouter, HTTPException, UploadFile, Form, Depends
from fastapi.responses import JSONResponse
from config import app, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from models import UserRegister, UserLogin, PasswordReset, VerifyResetCode, NewPassword
import random
from database import get_db
from utils import hash_password, send_reset_code
import cloudinary
import cloudinary.uploader
import logging
import asyncpg

router = APIRouter()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Cloudinary configuration
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)


@router.post("/register")
async def register(user: UserRegister, db: asyncpg.Pool = Depends(get_db)):
    """Register a new user with username, email, and hashed password."""
    async with db.acquire() as conn:
        hashed_password = hash_password(user.password)
        try:
            await conn.execute(
                "INSERT INTO users (username, email, password) VALUES ($1, $2, $3)",
                user.username, user.email, hashed_password
            )
            logger.info(f"User registered: {user.username}")
            return {"message": "Foydalanuvchi muvaffaqiyatli ro‘yxatdan o‘tdi"}
        except asyncpg.exceptions.UniqueViolationError:
            logger.warning(f"Registration failed for {user.username}: Username or email already exists")
            raise HTTPException(status_code=400, detail="Username yoki email allaqachon mavjud")


@router.post("/login")
async def login(user: UserLogin, db: asyncpg.Pool = Depends(get_db)):
    """Authenticate a user with username and password."""
    async with db.acquire() as conn:
        hashed_password = hash_password(user.password)
        result = await conn.fetchrow(
            "SELECT * FROM users WHERE username = $1 AND password = $2",
            user.username, hashed_password
        )
        if result:
            logger.info(f"User logged in: {user.username}")
            return {"message": "Kirish muvaffaqiyatli", "username": result["username"]}
        logger.warning(f"Login failed for {user.username}")
        raise HTTPException(status_code=401, detail="Username yoki parol noto‘g‘ri")


@router.post("/reset-password")
async def reset_password(data: PasswordReset, db: asyncpg.Pool = Depends(get_db)):
    """Generate and send a reset code to the user's email."""
    reset_code = ''.join(str(random.randint(0, 9)) for _ in range(6))
    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET reset_code = $1 WHERE email = $2",
            reset_code, data.email
        )
        if result == "UPDATE 0":
            logger.warning(f"Reset password failed: Email not found - {data.email}")
            raise HTTPException(status_code=404, detail="Email topilmadi")
        send_reset_code(data.email, reset_code)
        logger.info(f"Reset code sent to {data.email}")
        return {"message": "Tiklash kodi emailingizga yuborildi"}


@router.post("/verify-reset-code")
async def verify_reset_code(data: VerifyResetCode, db: asyncpg.Pool = Depends(get_db)):
    """Verify the reset code for a given email."""
    async with db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1 AND reset_code = $2",
            data.email, data.reset_code
        )
        if result:
            logger.info(f"Reset code verified for {data.email}")
            return {"message": "Kod to‘g‘ri"}
        logger.warning(f"Reset code verification failed for {data.email}")
        raise HTTPException(status_code=400, detail="Kod noto‘g‘ri yoki email topilmadi")


@router.post("/set-new-password")
async def set_new_password(data: NewPassword, db: asyncpg.Pool = Depends(get_db)):
    """Set a new password for the user after verification."""
    async with db.acquire() as conn:
        hashed_password = hash_password(data.new_password)
        result = await conn.execute(
            "UPDATE users SET password = $1, reset_code = NULL WHERE email = $2",
            hashed_password, data.email
        )
        if result == "UPDATE 0":
            logger.warning(f"Set new password failed: Email not found - {data.email}")
            raise HTTPException(status_code=404, detail="Email topilmadi")
        logger.info(f"New password set for {data.email}")
        return {"message": "Yangi parol muvaffaqiyatli o‘rnatildi"}


@router.get("/users")
async def get_users(query: str = "", db: asyncpg.Pool = Depends(get_db)):
    """Search for users by username with a query string."""
    async with db.acquire() as conn:
        users = await conn.fetch(
            "SELECT username FROM users WHERE username ILIKE $1",
            f"%{query}%"
        )
        logger.info(f"Users fetched with query: {query}")
        return [{"username": user["username"]} for user in users]
    
    # @router.get("/users")
# async def get_users(query: str = "", db=Depends(get_db)):
#     with db as conn:
#         cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
#         cursor.execute("SELECT username FROM users WHERE username ILIKE %s", (f"%{query}%",))
#         users = cursor.fetchall()
#         return [{"username": user["username"]} for user in users]


@router.post("/upload")
async def upload_file(file: UploadFile, sender: str = Form(...), receiver: str = Form(...)):
    """Upload a file to Cloudinary and return its URL."""
    logger.info(f"Upload request: sender={sender}, receiver={receiver}, file={file.filename}")
    try:
        upload_result = await cloudinary.uploader.upload(
            file.file,
            folder="chatapp_media",
            resource_type="auto"
        )
        file_url = upload_result["secure_url"]
        logger.info(f"Uploaded to Cloudinary: {file_url}")
        return {"file_url": file_url}
    except Exception as e:
        logger.error(f"Cloudinary upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cloudinary yuklash xatosi: {str(e)}")


app.include_router(router)