
FROM python:3.11-alpine


WORKDIR /app


RUN apk add --no-cache gcc musl-dev postgresql-dev


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8000


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
