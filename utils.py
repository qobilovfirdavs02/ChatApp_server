# utils.py
import hashlib
import random
import smtplib
from email.mime.text import MIMEText

# Parolni shifrlash
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Email orqali kod yuborish
def send_reset_code(email: str, reset_code: str):
    sender_email = "qobilovfirdavs2002@gmail.com"
    sender_password = "mwhqcmpfrdppskns"  # App Password
    msg = MIMEText(f"Sizning parolni tiklash kodingiz: {reset_code}")
    msg["Subject"] = "Parolni Tiklash"
    msg["From"] = sender_email
    msg["To"] = email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)