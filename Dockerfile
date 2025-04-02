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

# entrypoint.sh ni ishlatishga ruxsat berish
RUN chmod +x entrypoint.sh

# Portni ochish (hujjatlashtirish uchun)
EXPOSE 8000

# ENTRYPOINT bilan skriptni ishlatish
ENTRYPOINT ["./entrypoint.sh"]