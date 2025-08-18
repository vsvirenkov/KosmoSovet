import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram import F
from dotenv import load_dotenv
import os

load_dotenv()  # Загружает .env

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("API_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")  # ← от Yandex Cloud
FOLDER_ID = os.getenv("FOLDER_ID")  # ← в консоли Yandex Cloud → Облако → "Идентификатор"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Знаки зодиака
ZODIAC_SIGNS = {
    "Овен": "♈",
    "Телец": "♉",
    "Близнецы": "♊",
    "Рак": "♋",
    "Лев": "♌",
    "Дева": "♍",
    "Весы": "♎",
    "Скорпион": "♏",
    "Стрелец": "♐",
    "Козерог": "♑",
    "Водолей": "♒",
    "Рыбы": "♓"
}

user_zodiac = {}  # временно хранит знак пользователя

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

    Используй разговорный стиль, сленг, метафоры из жизни (доставка, чаты, кофе, Wi-Fi).
    Не более 110 слов. Без шаблонов. На русском.

    Пример (не копировать!):
    > 💼 Карьера: Сегодня твой шеф будет смотреть на тебя, как на пятно на стене. Используй это — работай меньше.
    > ❤️ Любовь: Ты привлекаешь внимание, как уведомление в 3 ночи. Надоело — отключи.
    > 🍀 Удача: Найдёшь 10 рублей под диваном. На большее не рассчитывай.
    > 🧠 Совет дня: Не начинай ничего важного после 18:00 — особенно переписку с бывшим.
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
                    "messages": [
                        {
                            "role": "user",
                            "text": prompt
                        }
                    ]
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

# === ХЕНДЛЕРЫ ===
@dp.message(F.text == "/start")
async def start(message: types.Message):
    kb = [[types.KeyboardButton(text=name)] for name in ZODIAC_SIGNS.keys()]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

    await message.answer(
        "🌟 Привет! Я — @CosmoBot\n"
        "Выбери свой знак зодиака — и получи уникальный гороскоп от ИИ 🤖✨",
        reply_markup=keyboard
    )

@dp.message(F.text.in_(ZODIAC_SIGNS.keys()))
async def handle_zodiac(message: types.Message):
    zodiac = message.text
    user_zodiac[message.from_user.id] = zodiac
    emoji = ZODIAC_SIGNS[zodiac]

    await message.answer("🔮 Запрашиваю прогноз у Вселенной...")

    # Получаем гороскоп от нейросети
    horoscope = await get_horoscope_from_ai(zodiac)

    await message.answer(
        f"{emoji} **{zodiac}**\n\n"
        f"{horoscope}\n\n"
        f"💫 Прогноз сгенерирован ИИ. "
        f"Завтра будет новый — подпишись, чтобы не пропустить!",
        parse_mode="Markdown"
    )

@dp.message(F.text == "/horoscope")
async def manual_request(message: types.Message):
    zodiac = user_zodiac.get(message.from_user.id)
    if not zodiac:
        await message.answer("Сначала выбери свой знак зодиака!")
        return
    await message.answer("🔮 Генерирую новый прогноз...")
    horoscope = await get_horoscope_from_ai(zodiac)
    await message.answer(f"✨ Твой гороскоп:\n\n{horoscope}")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())