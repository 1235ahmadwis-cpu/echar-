"""
Echar — Ta'lim sohasi uchun AI-yordamchi Telegram bot
G'oya: to'g'ridan-to'g'ri javob bermasdan, qadam-baqadam tushuntirish orqali o'rgatish.

MVP funksiyalari (taqdimotdagi 2-bosqich reja asosida):
  - /start   -> bot bilan tanishish
  - /help    -> yordam
  - /test    -> tanlangan mavzu bo'yicha avtomatik test yaratish
  - oddiy matn xabar -> savolni qadam-baqadam tushuntirib yechish (hozircha matematika fani)

Ishlatilgan kutubxonalar:
  - python-telegram-bot (v21+, async)
  - anthropic (Claude API orqali "o'qituvchi" mantiqi)
"""

import logging
import os

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from anthropic import Anthropic

from config import TELEGRAM_TOKEN, ANTHROPIC_API_KEY, MODEL_NAME

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("echar_bot")

# Anthropic (Claude) mijozi — barcha AI so'rovlari shu orqali yuboriladi
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ---------------------------------------------------------------------------
# Tizim promptlari (system prompt) — Echar'ning "pedagogik shaxsi"
# ---------------------------------------------------------------------------

TUTOR_SYSTEM_PROMPT = """Sen Echar — o'zbek maktab va universitet talabalariga yordam beradigan AI-o'qituvchisan.

QOIDALAR (juda muhim):
1. Hech qachon tayyor javobni darhol berma. Har doim qadam-baqadam (step-by-step) tushuntir.
2. Har bir qadamda o'quvchidan "tushundingmi?" yoki oraliq savol so'rab, uning fikrlashini rag'batlantir.
3. Faqat oxirgi qadamda, o'quvchi barcha bosqichlarni ko'rgandan keyin, yakuniy javobni aniq yoz.
4. Til — o'zbek tili (agar o'quvchi boshqa tilda yozsa, shu tilda javob ber).
5. Matematika, fizika va tillarni tushuntirishda sodda, tushunarli misollardan foydalan.
6. Javoblaring qisqa va aniq bo'lsin — uzun insho emas, o'qituvchi kabi suhbat qur.
"""

TEST_SYSTEM_PROMPT = """Sen Echar — test generatori vazifasini bajarayapsan.
Berilgan fan va mavzu bo'yicha 5 ta ko'p tanlovli (4 variantli: A, B, C, D) test savoli tuz.
Har bir savoldan keyin to'g'ri javobni ko'rsat va bir qatorlik izoh yoz.
Format:
1) Savol matni
   A) ...
   B) ...
   C) ...
   D) ...
   To'g'ri javob: X — qisqa izoh

Faqat o'zbek tilida yoz. Ortiqcha kirish so'zlarsiz, to'g'ridan-to'g'ri testdan boshla.
"""

# Foydalanuvchi holatini eslab qolish (oddiy, xotirada — MVP uchun yetarli)
# Har bir chat_id uchun oxirgi suhbat tarixini saqlaydi (Claude'ga kontekst berish uchun)
user_histories: dict[int, list[dict]] = {}

MAX_HISTORY_MESSAGES = 10  # xotira shishib ketmasligi uchun cheklov


# ---------------------------------------------------------------------------
# Buyruqlar (Commands)
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/start` buyrug'i — botni tanishtirish."""
    user_histories[update.effective_chat.id] = []

    keyboard = ReplyKeyboardMarkup(
        [["📝 Test yaratish"], ["❓ Yordam"]],
        resize_keyboard=True,
    )

    await update.message.reply_text(
        "Salom! 👋 Men *Echar* — sizga uy vazifasi, test tayyorlash va "
        "til o'rganishda yordam beruvchi AI-yordamchiman.\n\n"
        "Men javobni darhol bermayman — qadam-baqadam tushuntirib, "
        "o'zingiz fikrlashingizga yordam beraman.\n\n"
        "📌 Savolingizni shunchaki yozing (masalan: matematika masalasi), "
        "men uni birga yechamiz.\n"
        "📌 Test kerak bo'lsa: /test buyrug'ini bosing.\n\n"
        "Qani, birinchi savolingizni yuboring!",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/help` buyrug'i."""
    await update.message.reply_text(
        "*Echar bilan qanday ishlash mumkin:*\n\n"
        "• Har qanday savol yoki masalani yozing — men qadam-baqadam "
        "tushuntirib beraman.\n"
        "• /test <fan> <mavzu> — shu mavzu bo'yicha 5 ta test savoli "
        "yarataman.\n"
        "   Masalan: `/test matematika kvadrat tenglamalar`\n"
        "• /start — suhbatni qaytadan boshlash\n",
        parse_mode="Markdown",
    )


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/test <fan> <mavzu>` — mavzu bo'yicha test generatsiya qiladi."""
    if not context.args:
        await update.message.reply_text(
            "Mavzuni ham yozing. Masalan:\n`/test matematika kvadrat tenglamalar`",
            parse_mode="Markdown",
        )
        return

    topic = " ".join(context.args)
    await update.message.chat.send_action("typing")

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1200,
            system=TEST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Mavzu: {topic}"}],
        )
        test_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        await update.message.reply_text(f"📝 *{topic}* mavzusi bo'yicha test:\n\n{test_text}",
                                         parse_mode="Markdown")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Test yaratishda xatolik")
        await update.message.reply_text(
            "Kechirasiz, test yaratishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
        )


# ---------------------------------------------------------------------------
# Oddiy matn xabarlar — asosiy "o'qituvchi" mantiqi
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchidan kelgan har qanday matnni Claude orqali qadam-baqadam tushuntiradi."""
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Tugmalar orqali kelgan maxsus buyruqlarni ushlab qolamiz
    if user_text == "📝 Test yaratish":
        await update.message.reply_text(
            "Qanday fan va mavzudan test kerak? Masalan:\n`/test fizika Nyuton qonunlari`",
            parse_mode="Markdown",
        )
        return
    if user_text == "❓ Yordam":
        await help_command(update, context)
        return

    history = user_histories.setdefault(chat_id, [])
    history.append({"role": "user", "content": user_text})
    history = history[-MAX_HISTORY_MESSAGES:]

    await update.message.chat.send_action("typing")

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=800,
            system=TUTOR_SYSTEM_PROMPT,
            messages=history,
        )
        answer = "".join(
            block.text for block in response.content if block.type == "text"
        )
        history.append({"role": "assistant", "content": answer})
        user_histories[chat_id] = history[-MAX_HISTORY_MESSAGES:]

        await update.message.reply_text(answer)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Javob berishda xatolik")
        await update.message.reply_text(
            "Kechirasiz, hozir javob bera olmadim. Birozdan so'ng qayta urinib ko'ring."
        )


# ---------------------------------------------------------------------------
# Botni ishga tushirish
# ---------------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "TELEGRAM_TOKEN topilmadi. .env faylida yoki server sozlamalarida o'rnating."
        )
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY topilmadi. .env faylida yoki server sozlamalarida o'rnating."
        )

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Echar bot ishga tushdi (polling rejimida)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
