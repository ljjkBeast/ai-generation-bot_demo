from typing import Optional

from pydantic import BaseModel


class GenerationRequest(BaseModel):
    provider: str
    model: str
    prompt: str


class UserCreate(BaseModel):
    name: str
    initial_balance: int = 0


class UserResponse(BaseModel):
    id: int
    name: str
    balance: int
    tariff_id: Optional[int]


class UserUpdate(BaseModel):
    name: str = None


class TariffResponse(BaseModel):
    id: int
    name: str
    price: int
    tokens: int


class GenerationResponse(BaseModel):
    id: int
    provider: str
    model: str
    prompt: str
    cost: int
    status: str
    user_id: int


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    type: str
    generation_id: Optional[int]


class BalanceAddRequest(BaseModel):
    amount: int


class TelegramUserRequest(BaseModel):
    telegram_id: int
    name: str
    tariff_name: str | None = None


class TelegramGenerationRequest(BaseModel):
    telegram_id: int
    provider: str
    model: str
    prompt: str