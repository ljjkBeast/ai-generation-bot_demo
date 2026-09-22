import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

BEL_URL = "http://127.0.0.1:8000"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class RegistrationState(StatesGroup):
    waiting_for_tariff = State()

class GenerationState(StatesGroup):
    waiting_for_prompt = State()

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    name = message.from_user.full_name

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEL_URL}/internal/telegram/user",
            json={
                "telegram_id": telegram_id,
                "name": name
            }
        )
    if response.status_code == 400:
        await state.update_data(
            telegram_id=telegram_id,
            name=name
        )

        await state.set_state(
            RegistrationState.waiting_for_tariff
        )

        await message.answer(
            "Выбери тариф для начала:",
            reply_markup=tariffs_keyboard()
        )
        return
    if response.status_code == 400:
        await message.answer(
            "Выбери тариф для начала:",
            reply_markup=tariffs_keyboard()
        )
        return

    response.raise_for_status()

    user = response.json()

    await message.answer(
        f"Привет, {user['name']}!\n"
        f"Баланс: {user['balance']} токенов.",
        reply_markup=main_menu()
    )


async def main():
    await dp.start_polling(bot)

@dp.message(Command("balance"))
async def balance(message: Message):
    telegram_id = message.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEL_URL}/internal/telegram/user/{telegram_id}"
        )

    if response.status_code == 404:
        await message.answer(
            "Пользователь не найден. "
            "Сначала отправь /start"
        )
        return

    response.raise_for_status()

    user = response.json()

    await message.answer(
        f"Баланс: {user['balance']}"
    )

@dp.message(F.text == "Баланс")
async def balance_button(message: Message):
    telegram_id = message.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEL_URL}/internal/telegram/user/{telegram_id}"
        )

    response.raise_for_status()

    user = response.json()

    await message.answer(
        f"Ваш баланс: {user['balance']} токенов."
    )

@dp.message(F.text == "Генерация")
async def generation_button(
    message: Message,
    state: FSMContext
):
    telegram_id = message.from_user.id

    keyboard = await models_keyboard(telegram_id)

    sent_message = await message.answer(
        "Выбери модель:",
        reply_markup=keyboard
    )

    await state.update_data(
        menu_message_id=sent_message.message_id
    )

@dp.callback_query(F.data.startswith("model:"))
async def model_selected(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()

    data = callback.data.split(":", 2)

    provider = data[1]
    model = data[2]

    await state.update_data(
        model=model,
        provider=provider
    )

    await state.set_state(
        GenerationState.waiting_for_prompt
    )

    cancel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="cancel_generation"
                )
            ]
        ]
    )

    model_message = await callback.message.answer(
        f"Выбрана модель: {model}\n\n"
        "Теперь напиши запрос:",
        reply_markup=cancel_keyboard
    )

    await state.update_data(
        model_message_id=model_message.message_id
    )

    await callback.answer()

@dp.callback_query(F.data == "cancel_generation")
async def cancel_generation(
    callback: CallbackQuery,
    state: FSMContext
):
    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await state.clear()

    await callback.message.answer(
        "Генерация отменена."
    )

    await callback.answer()

@dp.message(GenerationState.waiting_for_prompt)
async def generation_prompt(message: Message, state: FSMContext):
    await state.update_data(
        prompt_message_id=message.message_id
    )
    prompt = message.text.strip()

    if not prompt:
        await message.answer(
            "Запрос не может быть пустым."
        )
        return

    data = await state.get_data()

    model = data["model"]
    provider = data["provider"]

    telegram_id = message.from_user.id

    await state.clear()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEL_URL}/internal/telegram/generate",
            json={
                "telegram_id": telegram_id,
                "provider": provider,
                "model": model,
                "prompt": prompt
            }
        )

    if response.status_code in (400, 404):
        data = response.json()

        await message.answer(
            f"Ошибка: {data['detail']}"
        )
        return

    response.raise_for_status()

    data = response.json()

    await message.answer(
        f"Генерация #{data['generation_id']} запущена.\n"
        f"Модель: {model}\n"
        f"Стоимость: {data['cost']} токенов."
    )

    asyncio.create_task(
        wait_for_generation(
            message,
            data["generation_id"]
        )
    )

async def models_keyboard(telegram_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEL_URL}/internal/telegram/models/{telegram_id}"
        )

    response.raise_for_status()

    models = response.json()

    buttons = []

    for item in models:
        buttons.append([
            InlineKeyboardButton(
                text=(
                    f"{item['model']} "
                    f"({item['cost']} токенов)"
                ),
                callback_data=(
                    f"model:"
                    f"{item['provider']}:"
                    f"{item['model']}"
                )
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

async def wait_for_generation(
    message: Message,
    generation_id: int
):
    for _ in range(12):
        await asyncio.sleep(1)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BEL_URL}/internal/telegram/"
                f"generation/{generation_id}"
            )

        response.raise_for_status()

        generation = response.json()

        if generation["status"] == "completed":
            await message.answer(
                f"Готово!\n\n"
                f"{generation['result']}"
            )
            return

        if generation["status"] == "failed":
            await message.answer(
                "Генерация не удалась. "
                "Токены возвращены."
            )
            return

    await message.answer(
        "Генерация выполняется слишком долго. "
        "Проверь историю позже."
    )

@dp.message(F.text == "История")
async def history_button(message: Message):
    telegram_id = message.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BEL_URL}/internal/telegram/"
            f"generations/{telegram_id}"
        )

    response.raise_for_status()

    generations = response.json()

    if not generations:
        await message.answer(
            "История генераций пуста."
        )
        return

    text = "Последние генерации:\n\n"

    for generation in generations[-10:]:
        text += (
            f"#{generation['id']} — "
            f"{generation['status']}\n"
            f"{generation['prompt']}\n\n"
        )

    await message.answer(text)

@dp.message(F.text == "Тариф")
async def tariff_button(message: Message):
    await message.answer(
        "Выбери тариф:",
        reply_markup=tariffs_keyboard()
    )

@dp.callback_query(F.data.startswith("tariff:"))
async def tariff_selected(
    callback: CallbackQuery,
    state: FSMContext
):
    tariff_name = callback.data.split(":", 1)[1]

    current_state = await state.get_state()

    if current_state == RegistrationState.waiting_for_tariff.state:
        data = await state.get_data()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BEL_URL}/internal/telegram/user",
                json={
                    "telegram_id": data["telegram_id"],
                    "name": data["name"],
                    "tariff_name": tariff_name
                }
            )

        response.raise_for_status()

        user = response.json()

        await state.clear()

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        await callback.message.answer(
            f"Регистрация завершена.\n"
            f"Тариф: {tariff_name}\n"
            f"Баланс: {user['balance']} токенов.",
            reply_markup=main_menu()
        )

        await callback.answer()
        return

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(
        f"Выбран тариф: {tariff_name}\n\n"
        "Подтвердить смену тарифа?",
        reply_markup=confirm_tariff_keyboard(tariff_name)
    )

    await callback.answer()


def confirm_tariff_keyboard(tariff_name: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=f"confirm_tariff:{tariff_name}"
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="cancel_tariff"
                )
            ]
        ]
    )

@dp.callback_query(F.data.startswith("confirm_tariff:"))
async def confirm_tariff(callback):
    await callback.message.edit_reply_markup(
        reply_markup=None
    )
    tariff_name = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BEL_URL}/internal/telegram/"
            f"tariff/{telegram_id}",
            params={
                "tariff_name": tariff_name
            }
        )

    if response.status_code == 404:
        await callback.message.answer(
            "Пользователь или тариф не найден."
        )
        await callback.answer()
        return

    response.raise_for_status()

    data = response.json()

    await callback.message.answer(
        f"Тариф изменён.\n\n"
        f"Текущий тариф: {data['tariff']}"
    )

    await callback.answer()

@dp.callback_query(F.data == "cancel_tariff")
async def cancel_tariff(callback):
    await callback.message.edit_reply_markup(
        reply_markup=None
    )
    await callback.message.answer(
        "Смена тарифа отменена."
    )

    await callback.answer()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Генерация"),
                KeyboardButton(text="Баланс")
            ],
            [
                KeyboardButton(text="Тариф"),
                KeyboardButton(text="История")
            ]
        ],
        resize_keyboard=True
    )

def tariffs_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Basic — 100 токенов",
                    callback_data="tariff:Basic"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Pro — 600 токенов",
                    callback_data="tariff:Pro"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Premium — 2000 токенов",
                    callback_data="tariff:Premium"
                )
            ]
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())

