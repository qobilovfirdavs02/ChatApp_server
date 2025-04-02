# Python image olish
FROM python:3.11-alpine

# Ishchi katalogni belgilash
WORKDIR /app

# Kerakli kutubxonalarni o‘rnatish
RUN apk add --no-cache gcc musl-dev postgresql-dev

# Requirements.txt ni konteynerga nusxalash
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyihani konteynerga nusxalash
COPY . .

# Portni ochish (hujjatlashtirish uchun, dinamik portga ta’sir qilmaydi)
EXPOSE 8000

# FastAPI serverni shell sintaksisida ishga tushirish
CMD uvicorn main:app --host 0.0.0.0 --port $PORT