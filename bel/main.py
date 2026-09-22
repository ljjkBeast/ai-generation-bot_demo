from fastapi import FastAPI
from fastapi import HTTPException, Depends
from typing import Optional, List
from sqlmodel import Session, select
from database import engine
from models import User, Generation, Tariff, Transaction, ModelPrice
from database import (create_db,
                      seed_database,
                      get_user_by_id,
                      get_generations_by_user_id,
                      get_user_with_generations,
                      seed_tariffs,
                      get_user_with_tariff,
                      seed_model_prices,
                      get_model_price,
                      buy_tariff,
                      change_user_tariff,
                      create_user,
                      update_user,
                      complete_generation,
                      refund_generation,
                      get_transactions_by_user_id,
                      get_balance_from_transactions,
                      check_user_balance,
                      add_balance,
                      get_model_prices_by_tariff,
                      create_web_session,
                      get_user_by_session_token,
                      get_user_by_telegram_id,
                      create_telegram_user,
                      get_generation_by_id,
                      get_tariff_by_id,
                      get_tariff_by_name)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from schemas import (
    GenerationRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
    TariffResponse,
    GenerationResponse,
    TransactionResponse,
    BalanceAddRequest,
    TelegramUserRequest,
    TelegramGenerationRequest,
)
from services import (
    send_generation_to_usa,
    start_generation,
)



app = FastAPI()
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    user = get_user_by_session_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid session token"
        )

    return user

@app.get("/")
async def root():
    message = "Hello FastAPI"

    return {
        "message": message
    }

@app.on_event("startup")
async def startup():
    create_db()
    seed_tariffs()
    seed_model_prices()
    seed_database()

@app.post("/me/generate")
async def generate(payload: GenerationRequest, user: User = Depends(get_current_user)):

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.tariff_id is None:
        raise HTTPException(
            status_code=400,
            detail="User has no tariff"
        )

    price = get_model_price(
        payload.provider,
        payload.model,
        user.tariff_id
    )

    if price is None:
        raise HTTPException(
            status_code=400,
            detail="Unknown provider or model"
        )

    cost = price.cost

    generation = await start_generation(
        user_id=user.id,
        payload=payload,
        cost=cost
    )

    usa_response = await send_generation_to_usa(
        user_id=user.id,
        generation_id=generation.id,
        provider=payload.provider,
        model=payload.model,
        prompt=payload.prompt
    )

    return {
        "generation": generation,
        "usa": usa_response
    }

def charge_generation(user_id: int, payload, cost: int):
    with Session(engine) as session:

        user = session.get(User, user_id)

        if user is None:
            return None, None, None, "user_not_found"

        if user.balance < cost:
            return None, None, None, "not_enough_balance"

        generation = Generation(
            provider=payload.provider,
            model=payload.model,
            prompt=payload.prompt,
            cost=cost,
            status="pending",
            user_id=user.id
        )

        session.add(generation)
        session.flush()

        user.balance -= cost

        transaction = Transaction(
            user_id=user.id,
            amount=-cost,
            type="generation_charge",
            generation_id=generation.id
        )

        session.add(transaction)

        session.commit()

        session.refresh(user)
        session.refresh(generation)
        session.refresh(transaction)

        return user, generation, transaction, None

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user

@app.get("/users/{user_id}/generations", response_model=List[GenerationResponse])
async def get_user_generations(user_id: int):
    user = get_user_with_generations(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user.generations

@app.get("/tariffs", response_model=List[TariffResponse])
async def get_tariffs():
    with Session(engine) as session:
        tariffs = session.exec(select(Tariff)).all()
        return tariffs

@app.get("/users/{user_id}/tariff")
async def get_user_tariff(user_id: int):
    user = get_user_with_tariff(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user.tariff

@app.get("/model-prices/{provider}/{model}")
async def get_price(provider: str, model: str):
    price = get_model_price(provider, model)

    if price is None:
        raise HTTPException(
            status_code=404,
            detail="Model price not found"
        )

    return price

@app.post("/users/{user_id}/buy-tariff/{tariff_id}")
async def buy_user_tariff(user_id: int, tariff_id: int):
    user, error = buy_tariff(user_id, tariff_id)

    if error == "user_not_found":
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if error == "tariff_not_found":
        raise HTTPException(
            status_code=404,
            detail="Tariff not found"
        )

    return user

@app.put("/users/{user_id}/tariff/{tariff_id}")
async def change_tariff(user_id: int, tariff_id: int):
    user, error = change_user_tariff(user_id, tariff_id)

    if error == "user_not_found":
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if error == "tariff_not_found":
        raise HTTPException(
            status_code=404,
            detail="Tariff not found"
        )

    return user

@app.post("/users", response_model=UserResponse)
async def create_new_user(payload: UserCreate):
    user = create_user(
        payload.name,
        payload.initial_balance
    )

    return user

@app.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: int,
    payload: UserUpdate
):
    data = payload.model_dump(exclude_unset=True)

    user, error = update_user(
        user_id,
        data
    )

    if error == "user_not_found":
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user

@app.get("/users/{user_id}/transactions",response_model=List[TransactionResponse])
async def get_user_transactions(user_id: int):
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    transactions = get_transactions_by_user_id(user_id)

    return transactions

@app.get("/users/{user_id}/calculated-balance")
async def get_calculated_balance(user_id: int):
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    balance = get_balance_from_transactions(user_id)

    return {
        "user_balance": user.balance,
        "calculated_balance": balance
    }

@app.get("/users/{user_id}/balance-check")
async def balance_check(user_id: int):

    result, error = check_user_balance(user_id)

    if error == "user_not_found":
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return result

@app.post("/users/{user_id}/balance")
async def add_user_balance(
    user_id: int,
    payload: BalanceAddRequest
):
    result = add_balance(
        user_id,
        payload.amount,
        "balance_topup"
    )

    user, transaction, error = result

    if error == "user_not_found":
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if error == "invalid_amount":
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    return {
        "user": user,
        "transaction": transaction
    }

@app.post("/internal/generations/{generation_id}/complete")
async def complete_generation_endpoint(generation_id: int, data: dict):
    generation = complete_generation(
        generation_id=generation_id,
        status=data["status"],
        result=data.get("result")
    )

    if generation is None:
        raise HTTPException(
            status_code=404,
            detail="Generation not found"
        )

    if data["status"] == "failed":
        refund_generation(generation_id)

    return {
        "status": "updated"
    }


@app.get("/users/{user_id}/models")
def get_user_models(user_id: int):
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.tariff_id is None:
        raise HTTPException(
            status_code=400,
            detail="User has no tariff"
        )

    prices = get_model_prices_by_tariff(user.tariff_id)

    return prices

@app.post("/login/{user_id}")
def login(user_id: int):
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    web_session = create_web_session(user_id)

    return {
        "user_id": user.id,
        "session_token": web_session.token
    }

@app.get("/me/balance")
def get_my_balance(
    user: User = Depends(get_current_user)
):
    return {
        "id": user.id,
        "name": user.name,
        "balance": user.balance
    }

@app.get("/me")
def get_me(
    user: User = Depends(get_current_user)
):
    return {
        "id": user.id,
        "name": user.name,
        "balance": user.balance,
        "tariff_id": user.tariff_id
    }

@app.get("/me/generations")
def get_my_generations(
    user: User = Depends(get_current_user)
):
    return get_generations_by_user_id(user.id)

@app.get("/me/tariff")
def get_my_tariff(
    user: User = Depends(get_current_user)
):
    user = get_user_with_tariff(user.id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.tariff is None:
        raise HTTPException(
            status_code=404,
            detail="User has no tariff"
        )

    return user.tariff

@app.get("/me/transactions")
def get_my_transactions(
    user: User = Depends(get_current_user)
):
    with Session(engine) as session:
        statement = select(Transaction).where(
            Transaction.user_id == user.id
        )

        return session.exec(statement).all()

@app.post("/internal/users")
def create_internal_user(
    name: str
):
    user = create_user(name)

    return {
        "id": user.id,
        "name": user.name,
        "balance": user.balance
    }

@app.post("/internal/telegram/user")
def telegram_user(
    payload: TelegramUserRequest
):
    user = get_user_by_telegram_id(
        payload.telegram_id
    )

    if user is not None:
        return user

    if payload.tariff_name is None:
        raise HTTPException(
            status_code=400,
            detail="Tariff is required for new user"
        )

    tariff = get_tariff_by_name(
        payload.tariff_name
    )

    if tariff is None:
        raise HTTPException(
            status_code=400,
            detail="Unknown tariff"
        )

    return create_telegram_user(
        telegram_id=payload.telegram_id,
        name=payload.name,
        tariff_id=tariff.id
    )

@app.get("/internal/telegram/user/{telegram_id}")
def get_telegram_user(telegram_id: int):
    user = get_user_by_telegram_id(telegram_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user

@app.post("/internal/telegram/generate")
async def telegram_generate(
    payload: TelegramGenerationRequest
):
    user = get_user_by_telegram_id(
        payload.telegram_id
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.tariff_id is None:
        raise HTTPException(
            status_code=400,
            detail="User has no tariff"
        )

    price = get_model_price(
        payload.provider,
        payload.model,
        user.tariff_id
    )

    if price is None:
        raise HTTPException(
            status_code=400,
            detail="Model not available"
        )

    generation = await start_generation(
        user_id=user.id,
        payload=payload,
        cost=price.cost
    )

    usa_response = await send_generation_to_usa(
        user_id=user.id,
        generation_id=generation.id,
        provider=payload.provider,
        model=payload.model,
        prompt=payload.prompt
    )

    return {
        "generation_id": generation.id,
        "status": generation.status,
        "cost": price.cost,
        "usa": usa_response
    }

@app.get("/internal/telegram/generation/{generation_id}")
def get_telegram_generation(
    generation_id: int
):
    generation = get_generation_by_id(
        generation_id
    )

    if generation is None:
        raise HTTPException(
            status_code=404,
            detail="Generation not found"
        )

    return generation

@app.get("/internal/telegram/generations/{telegram_id}")
def get_telegram_generations(telegram_id: int):
    user = get_user_by_telegram_id(telegram_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return get_generations_by_user_id(user.id)

@app.get("/internal/telegram/tariff/{telegram_id}")
def get_telegram_tariff(telegram_id: int):
    user = get_user_by_telegram_id(telegram_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    tariff = get_tariff_by_id(user.tariff_id)

    if tariff is None:
        raise HTTPException(
            status_code=404,
            detail="Tariff not found"
        )

    return tariff

@app.post("/internal/telegram/tariff/{telegram_id}")
def change_telegram_tariff(
    telegram_id: int,
    tariff_name: str
):
    user = get_user_by_telegram_id(telegram_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    with Session(engine) as session:
        tariff = session.exec(
            select(Tariff).where(
                Tariff.name == tariff_name
            )
        ).first()

        if tariff is None:
            raise HTTPException(
                status_code=404,
                detail="Tariff not found"
            )

        user.tariff_id = tariff.id

        session.add(user)
        session.commit()
        session.refresh(user)

        return {
            "message": "Tariff changed",
            "tariff": tariff.name,
            "tariff_id": tariff.id
        }

@app.get("/internal/telegram/models/{telegram_id}")
def get_telegram_models(telegram_id: int):
    user = get_user_by_telegram_id(telegram_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    with Session(engine) as session:
        statement = select(ModelPrice).where(
            ModelPrice.tariff_id == user.tariff_id
        )

        prices = session.exec(statement).all()

        return [
            {
                "provider": price.provider,
                "model": price.model,
                "cost": price.cost
            }
            for price in prices
        ]