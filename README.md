# AI Generation Bot

Учебный проект сервиса генерации контента через Telegram-бота.

Проект построен как связка из двух серверных частей:

* **BEL** — основной FastAPI-сервис, который отвечает за пользователей, баланс, тарифы, генерации и базу данных.
* **USA** — Telegram-бот и сервис генерации, который принимает пользовательские запросы и взаимодействует с AI-провайдерами.

Сейчас проект представляет собой рабочий прототип с регистрацией пользователей, тарифами, токенами, историей генераций и интеграцией с Google Gemini.

---

## Architecture

```text
                    Telegram
                       │
                       ▼
                ┌─────────────┐
                │  USA / Bot  │
                │   aiogram   │
                └──────┬──────┘
                       │ HTTP
                       ▼
                ┌─────────────┐
                │ BEL / API   │
                │   FastAPI   │
                └──────┬──────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
        ┌─────────┐        ┌────────────┐
        │ SQLite  │        │  USA API   │
        │Database │        │ Generation │
        └─────────┘        └─────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │ Google      │
                          │ Gemini API  │
                          └─────────────┘
```

### BEL

BEL является основной бизнес-логикой приложения.

Отвечает за:

* регистрацию Telegram-пользователей;
* пользователей и их баланс;
* тарифы;
* стоимость моделей;
* списание токенов;
* возврат токенов при ошибке генерации;
* создание записей генераций;
* историю генераций;
* транзакции;
* внутреннее API для Telegram-бота.

### USA

USA отвечает за Telegram-интерфейс и выполнение генераций.

Отвечает за:

* Telegram-бота на aiogram 3;
* команды и inline-кнопки;
* пользовательские сценарии;
* выбор тарифа;
* выбор AI-модели;
* отправку запросов на BEL;
* запуск генерации;
* polling статуса генерации;
* получение результата;
* взаимодействие с AI-провайдерами.

---

## Project Structure

```text
ai-generation-bot/
│
├── bel/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   └── services.py
│
├── usa/
│   ├── api.py
│   ├── bot.py
│   └── services.py
│
├── provider_server.py
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Tech Stack

### Backend

* Python 3.12
* FastAPI
* Uvicorn
* SQLModel
* SQLAlchemy
* SQLite

### Telegram

* aiogram 3
* FSM
* InlineKeyboard

### HTTP

* httpx
* aiohttp

### AI

* Google Gemini API
* `google-genai`

### Development

* PyCharm
* Git / GitHub
* Python virtual environment

---

## Main Features

### Telegram registration

При первом запуске бота пользователь автоматически регистрируется через BEL.

В BEL сохраняются:

* Telegram ID;
* имя пользователя;
* тариф;
* баланс токенов.

Повторный `/start` не создаёт нового пользователя.

---

### Tariffs

В проекте предусмотрены тарифы с различным количеством токенов.

Пользователь может:

* посмотреть доступные тарифы;
* выбрать тариф;
* изменить тариф.

---

### Token system

Каждая генерация имеет стоимость в токенах.

Перед запуском генерации BEL:

1. проверяет пользователя;
2. проверяет баланс;
3. создаёт генерацию;
4. списывает стоимость;
5. создаёт транзакцию.

Если генерация завершается ошибкой, токены возвращаются пользователю.

---

### Generation flow

Общий flow генерации:

```text
Telegram user
      │
      ▼
     Bot
      │
      │ POST /internal/telegram/generate
      ▼
     BEL
      │
      ├── validate user
      ├── check balance
      ├── create generation
      ├── charge tokens
      └── create transaction
      │
      ▼
     USA API
      │
      ├── select provider
      ├── call AI model
      └── return result
      │
      ▼
     BEL
      │
      └── update generation status
      │
      ▼
     Bot
      │
      └── send result to user
```

---

## Generation Status

Генерация создаётся со статусом:

```text
pending
```

После обработки статус обновляется в зависимости от результата.

При успешной генерации пользователь получает ответ модели.

При ошибке:

* генерация помечается как неуспешная;
* списанные токены возвращаются.

---

## Google Gemini

Проект подключён к Google Gemini API.

API key хранится в переменной окружения:

```env
GEMINI_API_KEY=your_api_key
```

API key не хранится непосредственно в исходном коде.

---

## Environment Variables

Создайте файл `.env` в корне проекта:

```env
BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
```

`.env` добавлен в `.gitignore` и не должен попадать в Git.

Для нового окружения можно использовать `.env.example` как шаблон.

---

## Installation

Клонировать репозиторий:

```bash
git clone <repository-url>
cd ai-generation-bot
```

Создать виртуальное окружение:

```bash
python3 -m venv .venv
```

Активировать:

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

Установить зависимости:

```bash
pip install -r requirements.txt
```

Создать `.env` и указать необходимые ключи.

---

## Running

### BEL

Запустить FastAPI:

```bash
uvicorn bel.main:app --reload --port 8000
```

После запуска API доступен локально по адресу:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

### USA Bot

В отдельном терминале:

```bash
python usa/bot.py
```

Таким образом одновременно работают:

```text
BEL API
  │
  │ HTTP
  ▼
USA Bot
```

---

## API

BEL предоставляет внутренние endpoints для взаимодействия с Telegram-ботом.

Основные операции:

```text
POST /internal/telegram/user
GET  /internal/telegram/user/{telegram_id}

GET  /internal/telegram/models/{telegram_id}

POST /internal/telegram/generate

GET  /internal/telegram/generation/{generation_id}

GET  /internal/telegram/generations/{telegram_id}

POST /internal/telegram/tariff/{telegram_id}
```

Конкретные параметры и схемы запросов доступны через Swagger после запуска BEL.

---

## Database

Для хранения данных используется SQLite.

Основные сущности проекта включают:

* users;
* tariffs;
* generations;
* transactions.

Связи между сущностями используются для хранения истории генераций и операций с балансом.

Локальная база данных не должна добавляться в Git.

---

## Error Handling

Проект обрабатывает основные ошибки бизнес-логики:

* пользователь не найден;
* недостаточно токенов;
* неизвестный тариф;
* неизвестная модель;
* ошибка AI-провайдера;
* ошибка генерации;
* HTTP-ошибки между сервисами.

При ошибке генерации предусмотрен возврат списанных токенов.

---

## Current State

Текущая версия проекта является рабочим прототипом.

Реализовано:

* [x] Telegram bot
* [x] Telegram user registration
* [x] FastAPI backend
* [x] SQLite database
* [x] Users
* [x] Tariffs
* [x] Token balance
* [x] Transactions
* [x] Generation history
* [x] Model selection
* [x] Token charging
* [x] Token refund on generation failure
* [x] Generation status polling
* [x] Google Gemini integration
* [x] Internal HTTP API between services

---

## Future Improvements

Планируемые направления развития:

* рефакторинг Telegram handlers;
* дальнейшее разделение бизнес-логики и HTTP-слоя;
* улучшение структуры сервисов;
* более чистая конфигурация приложения;
* полноценная работа с несколькими AI-провайдерами;
* расширение типов генерации;
* улучшение обработки ошибок;
* тесты;
* Docker;
* deployment;
* production database;
* authentication между внутренними сервисами.

---

