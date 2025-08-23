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

# Храним активные задачи: {user_id: задача}
active_tasks = {}

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
    try:
        while True:
            now = datetime.now(MOSCOW_TZ)
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

            sleep_seconds = (next_run - now).total_seconds()
            print(f"⏰ {zodiac} | Следующая рассылка через {sleep_seconds:.0f} секунд")
            await asyncio.sleep(sleep_seconds)

            await send_daily_horoscope(user_id, zodiac)
    except asyncio.CancelledError:
        print(f"🛑 Задача для пользователя {user_id} отменена")
        if user_id in active_tasks:
            del active_tasks[user_id]
        raise  # Обязательно


# === КОГДА ПОЛЬЗОВАТЕЛЬ ВЫБИРАЕТ ЗНАК ===
@dp.message(F.text.in_(ZODIAC_SIGNS.keys()))
async def set_zodiac(message: types.Message):
    user_id = message.from_user.id
    zodiac = message.text
    users[user_id] = zodiac

    # Сохраняем пользователя
    save_users()

    # Если у этого пользователя уже есть активная задача — отменяем её
    if user_id in active_tasks:
        active_tasks[user_id].cancel()
        print(f"🔄 Перезапуск задачи для пользователя {user_id}")

    # Запускаем новую задачу и сохраняем её в словарь
    task = asyncio.create_task(daily_horoscope_loop(user_id, zodiac))
    active_tasks[user_id] = task

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
        "🌟 Привет! Я — @KosmoSovetBot\n"
        "Выбери свой знак зодиака — и получай **смешной гороскоп от ИИ каждое утро** 🌅",
        reply_markup=keyboard
    )


# === /stop ===
@dp.message(F.text == "/stop")
async def stop_horoscope(message: types.Message):
    user_id = message.from_user.id
    if user_id in users:
        del users[user_id]
        save_users()  # сохранение пользователей
        await message.answer("🛑 Рассылка остановлена. Пришли /start, чтобы возобновить.")
    else:
        await message.answer("Ты и так не подписан.")

# === /ask ===
@dp.message(F.text.startswith("/ask"))
async def ask_universe(message: types.Message):
    question = message.text[len("/ask"):].strip()
    if not question:
        await message.answer("Напиши вопрос. Например: /ask стоит ли мне сменить работу?")
        return

    prompt = f"""
Ты — Вселенная, которая видит всё, но отвечает с иронией и мудростью.
На вопрос "{question}" ответь в одном предложении, как мем, но с глубоким смыслом.
Стиль: как у циничного философа из чата.
Пример: "Ты не опоздал — ты создал напряжение для драматического входа."
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
                answer = data["result"]["alternatives"][0]["message"]["text"]
            else:
                answer = "🌌 Вселенная молчит... Попробуй позже."

        except Exception as e:
            print(f"❌ Ошибка YandexGPT: {e}")
            answer = "⚠️ Не удалось связаться с космосом. Попробуй позже."

    # ✅ Отправляем ответ пользователю
    await message.answer(f"🌌 Вселенная говорит:\n\n {answer}")

# === /stats ===
@dp.message(F.text == "/stats")
async def stats(message: types.Message):
    id = os.getenv("MY_TG_ID")
    if message.from_user.id == int(id):  # ← твой ID в TG
        await message.answer(f"📊 Всего пользователей: {len(users)}")


# === СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЕЙ ===
import json

USERS_FILE = "users.json"
users = {}  # {user_id: zodiac}

def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        print(f"✅ Загружено пользователей: {len(users)}")
    except FileNotFoundError:
        users = {}
        print("📁 Файл users.json не найден. Создаётся новая база.")



# === ЗАПУСК ===
async def main():
    load_users()  # Загружаем пользователей
    print(f"✅ Загружено пользователей: {len(users)}")

    # Перезапускаем задачи для всех
    for user_id, zodiac in users.items():
        task = asyncio.create_task(daily_horoscope_loop(user_id, zodiac))
        active_tasks[user_id] = task

    print("🤖 Бот запущен. Ожидаем новых пользователей...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")