from sqlmodel import SQLModel, Session, create_engine, select, func
from typing import Optional
from models import User, Generation, Tariff, ModelPrice, Transaction, WebSession
import secrets
from schemas import TelegramGenerationRequest
DATABASE_URL = "sqlite:///database.db"

engine = create_engine(
    DATABASE_URL,
    echo=True
)


def create_db():
    SQLModel.metadata.create_all(engine)


def seed_database():
    with Session(engine) as session:

        users = session.exec(select(User)).all()

        if users:
            return

        basic = session.exec(
            select(Tariff).where(Tariff.name == "Basic")
        ).first()

        pro = session.exec(
            select(Tariff).where(Tariff.name == "Pro")
        ).first()

        premium = session.exec(
            select(Tariff).where(Tariff.name == "Premium")
        ).first()

        ivan = User(
            name="Ivan",
            balance=100,
            tariff_id=basic.id
        )

        alex = User(
            name="Alex",
            balance=50,
            tariff_id=pro.id
        )

        kate = User(
            name="Kate",
            balance=200,
            tariff_id=premium.id
        )

        session.add_all([
            ivan,
            alex,
            kate
        ])

        session.flush()

        transactions = [
            Transaction(
                user_id=ivan.id,
                amount=100,
                type="initial_balance"
            ),
            Transaction(
                user_id=alex.id,
                amount=50,
                type="initial_balance"
            ),
            Transaction(
                user_id=kate.id,
                amount=200,
                type="initial_balance"
            )
        ]

        session.add_all(transactions)

        session.commit()

def get_user_by_id(user_id: int):
    with Session(engine) as session:
        statement = select(User).where(User.id == user_id)
        user = session.exec(statement).first()

        return user

def create_user(name: str):
    with Session(engine) as session:
        basic = session.exec(
            select(Tariff).where(
                Tariff.name == "Basic"
            )
        ).first()

        if basic is None:
            raise ValueError(
                "Basic tariff not found"
            )

        user = User(
            name=name,
            balance=basic.tokens,
            tariff_id=basic.id
        )

        session.add(user)
        session.flush()

        transaction = Transaction(
            user_id=user.id,
            amount=basic.tokens,
            type="initial_balance"
        )

        session.add(transaction)

        session.commit()
        session.refresh(user)

        return user

def update_user(user_id: int, data: dict):
    with Session(engine) as session:
        user = session.get(User, user_id)

        if user is None:
            return None, "user_not_found"

        for field, value in data.items():
            setattr(user, field, value)

        session.commit()
        session.refresh(user)

        return user, None

def get_user_with_generations(user_id: int):
    with Session(engine) as session:
        statement = select(User).where(User.id == user_id)
        user = session.exec(statement).first()

        if user is None:
            return None

        user.generations

        return user

def get_user_by_session_token(token: str):
    with Session(engine) as session:
        statement = select(WebSession).where(
            WebSession.token == token
        )

        web_session = session.exec(statement).first()

        if web_session is None:
            return None

        user = session.get(
            User,
            web_session.user_id
        )

        return user

def get_user_with_tariff(user_id: int):
    with Session(engine) as session:
        statement = select(User).where(User.id == user_id)
        user = session.exec(statement).first()

        if user is None:
            return None

        user.tariff

        return user



def charge_generation(
    user_id: int,
    payload: TelegramGenerationRequest,
    cost: int
):
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
    
def get_generation_by_id(generation_id: int):
    with Session(engine) as session:
        return session.get(
            Generation,
            generation_id
        )

def get_generations_by_user_id(user_id: int):
    with Session(engine) as session:
        statement = select(Generation).where(
            Generation.user_id == user_id
        )

        generations = session.exec(statement).all()

        return generations

def update_generation_status(
    generation_id: int,
    status: str
):
    with Session(engine) as session:
        generation = session.get(
            Generation,
            generation_id
        )

        if generation is None:
            return None

        generation.status = status

        session.add(generation)
        session.commit()
        session.refresh(generation)

        return generation

def complete_generation(
    generation_id: int,
    status: str,
    result: str | None = None
):
    with Session(engine) as session:
        generation = session.get(
            Generation,
            generation_id
        )

        if generation is None:
            return None

        generation.status = status
        generation.result = result

        session.add(generation)
        session.commit()
        session.refresh(generation)

        return generation

def refund_generation(generation_id: int):
    with Session(engine) as session:
        generation = session.get(
            Generation,
            generation_id
        )

        if generation is None:
            return None, "generation_not_found"

        user = session.get(
            User,
            generation.user_id
        )

        if user is None:
            return None, "user_not_found"

        statement = select(Transaction).where(
            Transaction.generation_id == generation.id,
            Transaction.type == "generation_refund"
        )

        refund = session.exec(statement).first()

        if refund is not None:
            return None, "already_refunded"

        user.balance += generation.cost

        transaction = Transaction(
            user_id=user.id,
            amount=generation.cost,
            type="generation_refund",
            generation_id=generation.id
        )

        session.add(transaction)
        session.commit()

        session.refresh(user)
        session.refresh(transaction)

        return user, transaction


def seed_tariffs():
    with Session(engine) as session:
        tariffs = session.exec(select(Tariff)).all()

        if tariffs:
            return

        tariffs = [
            Tariff(
                name="Basic",
                price=100,
                tokens=100
            ),
            Tariff(
                name="Pro",
                price=500,
                tokens=600
            ),
            Tariff(
                name="Premium",
                price=1500,
                tokens=2000
            ),
        ]

        session.add_all(tariffs)
        session.commit()

def get_tariff_by_id(tariff_id: int):
    with Session(engine) as session:
        return session.get(
            Tariff,
            tariff_id
        )

def get_tariff_by_name(name: str):
    with Session(engine) as session:
        statement = select(Tariff).where(
            Tariff.name == name
        )

        return session.exec(statement).first()

def buy_tariff(user_id: int, tariff_id: int):
    with Session(engine) as session:
        user = session.get(User, user_id)

        if user is None:
            return None, "user_not_found"

        tariff = session.get(Tariff, tariff_id)

        if tariff is None:
            return None, "tariff_not_found"

        user.tariff_id = tariff.id
        user.balance += tariff.tokens

        session.add(user)
        session.commit()
        session.refresh(user)

        return user, None

def change_user_tariff(user_id: int, tariff_id: int):
    with Session(engine) as session:
        user = session.get(User, user_id)

        if user is None:
            return None, "user_not_found"

        tariff = session.get(Tariff, tariff_id)

        if tariff is None:
            return None, "tariff_not_found"

        user.tariff_id = tariff.id

        session.add(user)
        session.commit()
        session.refresh(user)

        return user, None


def add_balance(
    user_id: int,
    amount: int,
    transaction_type: str
):
    with Session(engine) as session:

        user = session.get(User, user_id)

        if user is None:
            return None, "user_not_found"

        if amount <= 0:
            return None, "invalid_amount"

        user.balance += amount

        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type=transaction_type
        )

        session.add(transaction)

        session.commit()

        session.refresh(user)
        session.refresh(transaction)

        return user, transaction, None

def subtract_balance(
    user_id: int,
    amount: int,
    transaction_type: str,
    generation_id: Optional[int] = None
):
    with Session(engine) as session:

        user = session.get(User, user_id)

        if user is None:
            return None, None, "user_not_found"

        if amount <= 0:
            return None, None, "invalid_amount"

        if user.balance < amount:
            return None, None, "not_enough_balance"

        user.balance -= amount

        transaction = Transaction(
            user_id=user.id,
            amount=-amount,
            type=transaction_type,
            generation_id=generation_id
        )

        session.add(transaction)

        session.commit()

        session.refresh(user)
        session.refresh(transaction)

        return user, transaction, None

def create_transaction(
    user_id: int,
    amount: int,
    transaction_type: str,
    generation_id: Optional[int] = None
):
    with Session(engine) as session:
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            type=transaction_type,
            generation_id=generation_id
        )

        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        return transaction

def get_balance_from_transactions(user_id: int):
    with Session(engine) as session:
        statement = select(
            func.coalesce(func.sum(Transaction.amount),0)
        ).where(Transaction.user_id == user_id)

        balance = session.exec(statement).one()

        return balance

def check_user_balance(user_id: int):
    with Session(engine) as session:

        user = session.get(User, user_id)

        if user is None:
            return None, "user_not_found"

        statement = select(
            func.coalesce(
                func.sum(Transaction.amount),
                0
            )
        ).where(
            Transaction.user_id == user_id
        )

        calculated_balance = session.exec(statement).one()

        if user.balance != calculated_balance:
            return {
                "user_balance": user.balance,
                "calculated_balance": calculated_balance,
                "consistent": False
            }, None

        return {
            "user_balance": user.balance,
            "calculated_balance": calculated_balance,
            "consistent": True
        }, None

def get_transaction_balance(user_id: int):
    with Session(engine) as session:
        statement = select(Transaction).where(
            Transaction.user_id == user_id
        )

        transactions = session.exec(statement).all()

        balance = 0

        for transaction in transactions:
            balance += transaction.amount

        return balance

def get_transactions_by_user_id(user_id: int):
    with Session(engine) as session:
        statement = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.id.desc())
        )

        transactions = session.exec(statement).all()

        return transactions


def seed_model_prices():
    with Session(engine) as session:
        prices = session.exec(select(ModelPrice)).all()

        if prices:
            return

        basic = session.exec(
            select(Tariff).where(Tariff.name == "Basic")
        ).first()

        pro = session.exec(
            select(Tariff).where(Tariff.name == "Pro")
        ).first()

        premium = session.exec(
            select(Tariff).where(Tariff.name == "Premium")
        ).first()
        prices = [
            ModelPrice(
                provider="openai",
                model="gpt-4_demo",
                cost=80,
                tariff_id=basic.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-4_demo",
                cost=60,
                tariff_id=pro.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-4_demo",
                cost=40,
                tariff_id=premium.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-3.5_demo",
                cost=20,
                tariff_id=basic.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-3.5_demo",
                cost=15,
                tariff_id=pro.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-3.5_demo",
                cost=10,
                tariff_id=premium.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-4o_demo",
                cost=70,
                tariff_id=basic.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-4o_demo",
                cost=50,
                tariff_id=pro.id
            ),
            ModelPrice(
                provider="openai",
                model="gpt-4o_demo",
                cost=30,
                tariff_id=premium.id
            ),
            ModelPrice(
                provider="google",
                model="gemini-3.5-flash-lite",
                cost=70,
                tariff_id=basic.id
            ),
            ModelPrice(
                provider="google",
                model="gemini-3.5-flash-lite",
                cost=50,
                tariff_id=pro.id
            ),
            ModelPrice(
                provider="google",
                model="gemini-3.5-flash-lite",
                cost=30,
                tariff_id=premium.id
            ),
        ]

        session.add_all(prices)
        session.commit()

def get_model_price(
    provider: str,
    model: str,
    tariff_id: int
):
    with Session(engine) as session:
        statement = select(ModelPrice).where(
            ModelPrice.provider == provider,
            ModelPrice.model == model,
            ModelPrice.tariff_id == tariff_id
        )

        price = session.exec(statement).first()

        return price

def get_model_prices_by_tariff(tariff_id: int):
    with Session(engine) as session:
        statement = select(ModelPrice).where(
            ModelPrice.tariff_id == tariff_id
        )

        return session.exec(statement).all()


def create_web_session(user_id: int):
    with Session(engine) as session:
        token = secrets.token_urlsafe(32)

        web_session = WebSession(
            token=token,
            user_id=user_id
        )

        session.add(web_session)
        session.commit()
        session.refresh(web_session)

        return web_session


def get_user_by_telegram_id(telegram_id: int):
    with Session(engine) as session:
        statement = select(User).where(
            User.telegram_id == telegram_id
        )

        return session.exec(statement).first()

def create_telegram_user(
    telegram_id: int,
    name: str,
    tariff_id: int
):
    with Session(engine) as session:
        tariff = session.get(Tariff, tariff_id)

        if tariff is None:
            raise ValueError("Tariff not found")

        user = User(
            telegram_id=telegram_id,
            name=name,
            balance=tariff.tokens,
            tariff_id=tariff.id
        )

        session.add(user)
        session.flush()

        transaction = Transaction(
            user_id=user.id,
            amount=tariff.tokens,
            type="initial_balance"
        )

        session.add(transaction)

        session.commit()
        session.refresh(user)

        return user