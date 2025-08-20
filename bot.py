import asyncio
from datetime import datetime, timedelta
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram import F
import aiohttp

from dotenv import load_dotenv
import os
load_dotenv()  # Загружает .env

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("API_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")  # ← от Yandex Cloud
FOLDER_ID = os.getenv("FOLDER_ID")  # ← в консоли Yandex Cloud → Облако → "Идентификатор"

# Часовой пояс
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Знаки зодиака
ZODIAC_SIGNS = {
    "Овен": "♈", "Телец": "♉", "Близнецы": "♊", "Рак": "♋",
    "Лев": "♌", "Дева": "♍", "Весы": "♎", "Скорпион": "♏",
    "Стрелец": "♐", "Козерог": "♑", "Водолей": "♒", "Рыбы": "♓"
}

# Хранилище пользователей: {user_id: zodiac}
users = {}


# === ФУНКЦИЯ: запрос к YandexGPT ===
async def get_horoscope_from_ai(zodiac_sign):
    prompt = f"""
Ты — ироничный, остроумный астролог с чувством абсурда.
Пиши гороскоп для знака {zodiac_sign} так, будто ты видел всё: и его переписку с мамой, и историю браузера.
Формат:
- 💼 Карьера (с сарказмом)
- ❤️ Любовь (с намёком на катастрофу или чудо)
- 🍀 Удача (в духе "повезёт, но не тебе")
- 🧠 Совет дня (одно предложение — как мем, но с глубиной)

Используй разговорный стиль, сленг, метафоры из жизни.
Не более 110 слов. Без шаблонов. На русском.
""".strip()

    async with aiohttp.ClientSession() as session:
        try:
            resp = await session.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers={
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite/latest",
                    "completionOptions": {
                        "temperature": 0.6,
                        "maxTokens": "500"
                    },
                    "messages": [{"role": "user", "text": prompt}]
                }
            )
            data = await resp.json()
            if "result" in data:
                return data["result"]["alternatives"][0]["message"]["text"]
            else:
                return "🌌 Вселенная молчит... Попробуй позже."
        except Exception as e:
            print(f"Ошибка YandexGPT: {e}")
            return "⚠️ Не удалось связаться с космосом. Попробуй позже."


# === ОТПРАВКА ГОРОСКОПА ===
async def send_daily_horoscope(user_id: int, zodiac: str):
    try:
        horoscope = await get_horoscope_from_ai(zodiac)
        await bot.send_message(
            chat_id=user_id,
            text=f"🌅 Доброе утро, {ZODIAC_SIGNS[zodiac]} {zodiac}!\n\n"
                 f"{horoscope}\n\n"
                 f"💫 Прогноз сгенерирован ИИ. "
                 f"Не забудь проверить, не пришла ли твоя любовь с доставкой…",
            parse_mode="Markdown"
        )
        print(f"✅ [УСПЕХ] Гороскоп отправлен пользователю {user_id}")
    except Exception as e:
        print(f"❌ [ОШИБКА] Не удалось отправить {user_id}: {e}")


# === ФОНОВЫЙ ЦИКЛ РАССЫЛКИ ===
async def daily_horoscope_loop(user_id: int, zodiac: str):
    """Фоновая задача: каждый день в 9:00 отправляет гороскоп"""
    while True:
        now = datetime.now(MOSCOW_TZ)
        # Время следующей отправки — 9:00
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)  # Если уже прошло — на завтра

        sleep_seconds = (next_run - now).total_seconds()
        print(f"⏰ {zodiac} | Следующая рассылка через {sleep_seconds:.0f} секунд (в {next_run.strftime('%H:%M')})")

        await asyncio.sleep(sleep_seconds)
        await send_daily_horoscope(user_id, zodiac)


# === КОГДА ПОЛЬЗОВАТЕЛЬ ВЫБИРАЕТ ЗНАК ===
@dp.message(F.text.in_(ZODIAC_SIGNS.keys()))
async def set_zodiac(message: types.Message):
    user_id = message.from_user.id
    zodiac = message.text
    users[user_id] = zodiac

    # Запускаем фоновую задачу
    asyncio.create_task(daily_horoscope_loop(user_id, zodiac))

    await message.answer(
        f"{ZODIAC_SIGNS[zodiac]} Отлично! Ты — **{zodiac}**.\n\n"
        f"🌅 Теперь каждый день в 9:00 я буду присылать тебе новый гороскоп от ИИ! 🤖✨",
        reply_markup=types.ReplyKeyboardRemove()
    )


# === /start ===
@dp.message(F.text == "/start")
async def start(message: types.Message):
    kb = [[types.KeyboardButton(text=sign)] for sign in ZODIAC_SIGNS.keys()]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer(
        "🌟 Привет! Я — @CosmoBot\n"
        "Выбери свой знак зодиака — и получай **смешной гороскоп от ИИ каждое утро** 🌅",
        reply_markup=keyboard
    )


# === ЗАПУСК ===
async def main():
    print("🤖 Бот запущен. Ожидаем команды...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")