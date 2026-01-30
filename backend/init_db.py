import asyncio
from database import engine, Base
from models import UserWallet, PaymentOrder, TransactionLedger

async def init_db():
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized completely.")

if __name__ == "__main__":
    asyncio.run(init_db())
