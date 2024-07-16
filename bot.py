import logging
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import calendar
import sqlite3

# Токен вашого бота
TOKEN = '7086626446:AAGuT9DR8XNI_0AfQ-g9DIuO84BeexMQn5o'
# ID власника бота
OWNER_ID = 432530900  # Замініть це значення на ваш Telegram User ID

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Ініціалізація бота та диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Ініціалізація бази даних
conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT
    )
''')
conn.commit()

# Повідомлення на різних мовах
messages = {
    'en': {
        'morse_error': "Failed to find Morse code for the selected date. Please try again later!",
        'combo_error': "Failed to find combo cards for the selected date. Please try again later!",
        'combo_success': "Here is the combo card for the selected date: {url}",
        'stay_tuned': "Stay Tuned Clickers",
        'welcome': "Welcome, {user}! Press the button below to see the options:",
        'choose_language': "Please choose your language:",
        'check_users': "Check Users",
        'menu': "Menu"
    },
    'ua': {
        'morse_error': "Не вдалося знайти морзе-код для обраної дати. Повертайся пізніше!",
        'combo_error': "Не вдалося знайти комбо карти для обраної дати. Повертайся пізніше!",
        'combo_success': "Ось комбо картка для обраної дати: {url}",
        'stay_tuned': "Stay Tuned Clickers",
        'welcome': "Ласкаво просимо, {user}! Натисніть кнопку нижче, щоб побачити опції:",
        'choose_language': "Будь ласка, виберіть свою мову:",
        'check_users': "Перевірити користувачів",
        'menu': "Меню"
    },
    'pl': {
        'morse_error': "Nie udało się znaleźć kodu Morse'a na wybraną datę. Spróbuj ponownie później!",
        'combo_error': "Nie udało się znaleźć kart combo na wybraną datę. Spróbuj ponownie później!",
        'combo_success': "Oto karta combo na wybraną datę: {url}",
        'stay_tuned': "Stay Tuned Clickers",
        'welcome': "Witamy, {user}! Naciśnij przycisk poniżej, aby zobaczyć opcje:",
        'choose_language': "Proszę wybrać język:",
        'check_users': "Sprawdź użytkowników",
        'menu': "Menu"
    }
}


# Логування
class LoggingMiddleware:
    async def __call__(self, handler, event, data):
        logging.info(f"Processing event: {event}")
        return await handler(event, data)


dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())


def fetch_morse_code(date, lang):
    url = "https://hamster-kombat.org/daily-cipher"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    all_text = soup.get_text()

    date_blocks = {}
    current_date = None

    for line in all_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed_date = datetime.strptime(line, '%B %d')
            current_date = parsed_date.strftime('%B %d')
            date_blocks[current_date] = []
        except ValueError:
            if current_date:
                date_blocks[current_date].append(line)

    morse_code_lines = date_blocks.get(date, [])
    morse_code_text = "\n".join(morse_code_lines).strip()

    if not morse_code_text:
        raise ValueError(messages[lang]['morse_error'])

    return f"{date}\n{morse_code_text}"


def get_latest_combo_card_url(date, lang):
    formatted_date = date.strftime('%B %d, %Y')
    url = 'https://hamster-kombat.org/daily-combo-cards/'
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    card_block = soup.find(string=lambda text: text and formatted_date in text)
    if card_block:
        img_tag = card_block.find_next('img')
        if img_tag and 'src' in img_tag.attrs:
            return img_tag['src']
        else:
            raise Exception(messages[lang]['combo_error'])
    else:
        raise Exception(messages[lang]['combo_error'])


def create_calendar(year=None, month=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="ignore"))

    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    keyboard.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in days_of_week])

    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        buttons = [InlineKeyboardButton(text=str(day) if day != 0 else " ", callback_data=f"day:{day}:{month}:{year}")
                   for day in week]
        keyboard.row(*buttons)

    keyboard.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"prev-month:{month}:{year}"),
        InlineKeyboardButton(text="➡️", callback_data=f"next-month:{month}:{year}")
    )

    keyboard.row(InlineKeyboardButton(text="🔙 Back", callback_data="hamster_kombat"))
    return keyboard.as_markup()


async def process_calendar_selection(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Callback data: {callback_query.data}")
    _, day, month, year = callback_query.data.split(":")
    date = datetime(int(year), int(month), int(day))
    formatted_date = date.strftime('%B %d')

    try:
        data = await state.get_data()
        morse_code = data.get('morse_code', False)
        lang = data.get('lang', 'en')
        if morse_code:
            text = fetch_morse_code(formatted_date, lang)
        else:
            combo_card_url = get_latest_combo_card_url(date, lang)
            text = messages[lang]['combo_success'].format(url=combo_card_url)

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="🔙 Back", callback_data="hamster_kombat"))
        await bot.edit_message_text(text=text, chat_id=callback_query.from_user.id,
                                    message_id=callback_query.message.message_id, reply_markup=keyboard.as_markup())

        # Оновлення запису користувача у базі даних
        user_id = callback_query.from_user.id
        username = callback_query.from_user.username
        first_name = callback_query.from_user.first_name
        last_name = callback_query.from_user.last_name
        language_code = callback_query.from_user.language_code

        cursor.execute('''
            INSERT INTO users (id, username, first_name, last_name, language_code) 
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            language_code=excluded.language_code
        ''', (user_id, username, first_name, last_name, language_code))
        conn.commit()

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        await callback_query.answer(str(e), show_alert=True)


async def send_calendar(message: types.Message, state: FSMContext, edit=False, morse_code=False):
    logging.info(f"Sending calendar. Morse code: {morse_code}")
    message_text = "Please choose a date:"
    reply_markup = create_calendar()
    await state.update_data(morse_code=morse_code)

    if edit:
        await bot.edit_message_text(text=message_text, chat_id=message.chat.id, message_id=message.message_id,
                                    reply_markup=reply_markup)
    else:
        await bot.send_message(message.chat.id, text=message_text, reply_markup=reply_markup)


async def change_month(callback_query: types.CallbackQuery):
    logging.info(f"Callback data: {callback_query.data}")
    action, month, year = callback_query.data.split(":")
    month, year = int(month), int(year)

    if action == "prev-month":
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
    elif action == "next-month":
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1

    await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id,
                                        message_id=callback_query.message.message_id,
                                        reply_markup=create_calendar(year, month))
    await callback_query.answer()


async def start(message: types.Message, state: FSMContext):
    logging.info("Starting bot")

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    language_code = message.from_user.language_code

    cursor.execute('''
        INSERT INTO users (id, username, first_name, last_name, language_code) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        language_code=excluded.language_code
    ''', (user_id, username, first_name, last_name, language_code))
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"))
    keyboard.row(InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua"))
    keyboard.row(InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang_pl"))
    await bot.send_message(message.chat.id, text=messages['en']['choose_language'], reply_markup=keyboard.as_markup())


async def language_selection(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Language selected: {callback_query.data}")
    lang_code = callback_query.data.split("_")[1]
    await state.update_data(lang=lang_code)

    user_first_name = callback_query.from_user.first_name
    welcome_text = messages[lang_code]['welcome'].format(user=user_first_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Hamster Kombat 🐹", callback_data="hamster_kombat"))

    if callback_query.from_user.id == OWNER_ID:
        keyboard.row(InlineKeyboardButton(text=messages[lang_code]['check_users'], callback_data="check_users"))

    await bot.edit_message_text(text=welcome_text, chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id, reply_markup=keyboard.as_markup())
    await callback_query.answer()


async def hamster_kombat_button(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info("Hamster Kombat button pressed")
    data = await state.get_data()
    lang = data.get('lang', 'en')

    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    first_name = callback_query.from_user.first_name
    last_name = callback_query.from_user.last_name
    language_code = callback_query.from_user.language_code

    cursor.execute('''
        INSERT INTO users (id, username, first_name, last_name, language_code) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        language_code=excluded.language_code
    ''', (user_id, username, first_name, last_name, language_code))
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="Daily Combo Cards 🃏", callback_data="daily_combo_cards"),
        InlineKeyboardButton(text="Daily Morse Code 📡", callback_data="daily_morse_code")
    )
    keyboard.row(InlineKeyboardButton(text="🔙 Back", callback_data="back_to_language_selection"))
    keyboard.row(InlineKeyboardButton(text="Cancel ❌", callback_data="cancel"))
    await bot.edit_message_text(text=messages[lang]['stay_tuned'], chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id, reply_markup=keyboard.as_markup())
    await callback_query.answer()


async def daily_combo_cards(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    first_name = callback_query.from_user.first_name
    last_name = callback_query.from_user.last_name
    language_code = callback_query.from_user.language_code

    cursor.execute('''
        INSERT INTO users (id, username, first_name, last_name, language_code) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        language_code=excluded.language_code
    ''', (user_id, username, first_name, last_name, language_code))
    conn.commit()

    await send_calendar(callback_query.message, state=state, edit=True)


async def daily_morse_code(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    first_name = callback_query.from_user.first_name
    last_name = callback_query.from_user.last_name
    language_code = callback_query.from_user.language_code

    cursor.execute('''
        INSERT INTO users (id, username, first_name, last_name, language_code) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        language_code=excluded.language_code
    ''', (user_id, username, first_name, last_name, language_code))
    conn.commit()

    await send_calendar(callback_query.message, state=state, edit=True, morse_code=True)


async def back_to_language_selection(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info("Back to language selection")
    user_first_name = callback_query.from_user.first_name
    data = await state.get_data()
    lang_code = data.get('lang', 'en')

    welcome_text = messages[lang_code]['welcome'].format(user=user_first_name)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Hamster Kombat 🐹", callback_data="hamster_kombat"))

    if callback_query.from_user.id == OWNER_ID:
        keyboard.row(InlineKeyboardButton(text=messages[lang_code]['check_users'], callback_data="check_users"))

    await bot.edit_message_text(text=welcome_text, chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id, reply_markup=keyboard.as_markup())
    await callback_query.answer()


# Функція для обробки кнопки "Check Users"
async def check_users(callback_query: types.CallbackQuery):
    if callback_query.from_user.id == OWNER_ID:
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        users_info = '\n'.join(
            [f"ID: {user[0]}\nUsername: {user[1]}\nFirst name: {user[2]}\nLast name: {user[3]}\nLanguage: {user[4]}\n"
             for user in users])
        await callback_query.message.answer(f"Users:\n{users_info}")
    else:
        await callback_query.message.answer("You don't have permission to use this command.")
    await callback_query.answer()


# Реєстрація хендлерів
dp.message.register(start, Command(commands=["start"]))
dp.callback_query.register(process_calendar_selection, F.data.startswith('day:'))
dp.callback_query.register(change_month, F.data.startswith('prev-month') | F.data.startswith('next-month'))
dp.callback_query.register(language_selection, F.data.startswith('lang_'))
dp.callback_query.register(hamster_kombat_button, F.data == 'hamster_kombat')
dp.callback_query.register(daily_combo_cards, F.data == 'daily_combo_cards')
dp.callback_query.register(daily_morse_code, F.data == 'daily_morse_code')
dp.callback_query.register(back_to_language_selection, F.data == 'back_to_language_selection')
dp.callback_query.register(check_users, F.data == 'check_users')


# Головна функція для запуску бота
async def main():
    logging.info("Starting polling")
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())

