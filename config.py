"""
Echar bot sozlamalari.

Tokenlarni hech qachon kodga yozib qo'ymang! Ular .env faylidan
yoki serverning environment variables (muhit o'zgaruvchilari) bo'limidan o'qiladi.
"""

import os

from dotenv import load_dotenv

# Lokal ishga tushirishda .env faylini o'qish (serverda odatda
# environment variables to'g'ridan-to'g'ri panel orqali beriladi)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Foydalaniladigan Claude modeli. Kerak bo'lsa .env orqali almashtirish mumkin.
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-6")
