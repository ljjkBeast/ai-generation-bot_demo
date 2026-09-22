from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: int | None = Field(
        default=None,
        primary_key=True
    )

    name: str
    balance: int

    telegram_id: int | None = Field(
        default=None,
        unique=True,
        index=True
    )

    tariff_id: int | None = Field(
        default=None,
        foreign_key="tariff.id"
    )

    generations: List["Generation"] = Relationship(
        back_populates="user"
    )
    tariff: Optional["Tariff"] = Relationship(
        back_populates="users"
    )
    transactions: List["Transaction"] = Relationship(
        back_populates="user"
    )

class Generation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str
    model: str
    prompt: str
    cost: int
    status: str
    result: Optional[str] = None
    user_id: int = Field(foreign_key="user.id")

    user: Optional[User] = Relationship(back_populates="generations")
    transactions: List["Transaction"] = Relationship(
        back_populates="generation"
    )

class Tariff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    price: int
    tokens: int

    users: List["User"] = Relationship(
        back_populates="tariff"
    )
    model_prices: List["ModelPrice"] = Relationship(
        back_populates="tariff"
    )

class ModelPrice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    provider: str
    model: str
    cost: int

    tariff_id: int = Field(
        foreign_key="tariff.id"
    )

    tariff: Optional["Tariff"] = Relationship(
        back_populates="model_prices"
    )

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="user.id"
    )

    amount: int
    type: str
    generation_id: Optional[int] = Field(
        default=None,
        foreign_key="generation.id"
    )
    user: Optional[User] = Relationship(
        back_populates="transactions"
    )
    generation: Optional[Generation] = Relationship(
        back_populates="transactions"
    )

class WebSession(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    token: str = Field(index=True)
    user_id: int = Field(
        foreign_key="user.id"
    )