#!/bin/sh
# PORT ni o‘qiydi, agar yo‘q bo‘lsa 8000 ishlatadi
PORT=${PORT:-8000}
exec uvicorn main:app --host 0.0.0.0 --port $PORT