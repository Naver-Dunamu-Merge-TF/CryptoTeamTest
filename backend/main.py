from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from pydantic import BaseModel
from decimal import Decimal
from typing import List, Optional
import uuid

from database import get_db, engine, Base
from models import UserWallet, PaymentOrder, TransactionLedger

app = FastAPI()

# Pydantic Models
class BuyRequest(BaseModel):
    user_id: str
    amount: Decimal

class PayPrepareRequest(BaseModel):
    user_id: str
    merchant_name: str
    amount: Decimal

class PayConfirmRequest(BaseModel):
    order_id: str

class PayCancelRequest(BaseModel):
    order_id: str

class WalletResponse(BaseModel):
    user_id: str
    balance: Decimal
    frozen_amount: Decimal

class OrderResponse(BaseModel):
    order_id: str
    status: str
    frozen_amount: Decimal

# Core Logic Endpoints

@app.post("/api/buy")
async def buy_nsc(req: BuyRequest, db: AsyncSession = Depends(get_db)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # 1. Update Wallet
    result = await db.execute(select(UserWallet).where(UserWallet.user_id == req.user_id))
    wallet = result.scalars().first()

    if not wallet:
        wallet = UserWallet(user_id=req.user_id, balance=0, frozen_amount=0)
        db.add(wallet)
    
    wallet.balance += req.amount
    
    # 2. Add Ledger Entry
    ledger = TransactionLedger(wallet_id=req.user_id, type="BUY", amount=req.amount)
    db.add(ledger)
    
    await db.commit()
    return {"message": "NSC Purchased", "new_balance": wallet.balance}

@app.post("/api/pay/prepare")
async def prepare_payment(req: PayPrepareRequest, db: AsyncSession = Depends(get_db)):
    async with db.begin(): # Start Transaction
        # 1. Lock Wallet Row
        result = await db.execute(select(UserWallet).where(UserWallet.user_id == req.user_id).with_for_update())
        wallet = result.scalars().first()

        if not wallet:
             raise HTTPException(status_code=404, detail="Wallet not found")
        
        if wallet.balance < req.amount:
            raise HTTPException(status_code=400, detail="Insufficient Balance")

        # 2. Freeze Amount
        wallet.balance -= req.amount
        wallet.frozen_amount += req.amount
        
        # 3. Create Order
        order_id = str(uuid.uuid4())
        order = PaymentOrder(
            order_id=order_id,
            user_id=req.user_id,
            merchant_name=req.merchant_name,
            amount=req.amount,
            status="READY"
        )
        db.add(order)
        
    # Commit happens automatically on exit of `async with db.begin()`
    return {"status": "READY", "order_id": order_id, "frozen_amount": req.amount}

@app.post("/api/pay/confirm")
async def confirm_payment(req: PayConfirmRequest, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        # 1. Get Order
        result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_id == req.order_id).with_for_update())
        order = result.scalars().first()

        if not order or order.status != "READY":
            raise HTTPException(status_code=400, detail="Invalid Order")

        # 2. Get Wallet
        wallet_result = await db.execute(select(UserWallet).where(UserWallet.user_id == order.user_id).with_for_update())
        wallet = wallet_result.scalars().first()

        # 3. Deduct Frozen Amount (Permanent Settle)
        wallet.frozen_amount -= order.amount
        
        # 4. Update Order Status
        order.status = "COMPLETED"
        
        # 5. Ledger Entry
        ledger = TransactionLedger(
            wallet_id=order.user_id,
            type="PAY",
            amount=order.amount,
            related_id=order.order_id
        )
        db.add(ledger)

    return {"status": "COMPLETED", "order_id": order.order_id}

@app.post("/api/pay/cancel")
async def cancel_payment(req: PayCancelRequest, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        # 1. Get Order
        result = await db.execute(select(PaymentOrder).where(PaymentOrder.order_id == req.order_id).with_for_update())
        order = result.scalars().first()

        if not order or order.status != "READY":
            raise HTTPException(status_code=400, detail="Invalid Order for Cancellation")

        # 2. Get Wallet
        wallet_result = await db.execute(select(UserWallet).where(UserWallet.user_id == order.user_id).with_for_update())
        wallet = wallet_result.scalars().first()

        # 3. Refund Frozen Amount
        wallet.frozen_amount -= order.amount
        wallet.balance += order.amount
        
        # 4. Update Order Status
        order.status = "CANCELED"
        
        # 5. Ledger Entry
        ledger = TransactionLedger(
            wallet_id=order.user_id,
            type="REFUND",
            amount=order.amount,
            related_id=order.order_id
        )
        db.add(ledger)

    return {"status": "CANCELED", "order_id": order.order_id}

# View Endpoints

@app.get("/api/wallet/{user_id}")
async def get_wallet(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserWallet).where(UserWallet.user_id == user_id))
    wallet = result.scalars().first()
    
    if not wallet:
        # Create wallet if not exists for demo convenience
        wallet = UserWallet(user_id=user_id, balance=0, frozen_amount=0)
        db.add(wallet)
        await db.commit()
    
    # Get last 10 transactions
    ledger_res = await db.execute(select(TransactionLedger).where(TransactionLedger.wallet_id == user_id).order_by(TransactionLedger.created_at.desc()).limit(10))
    transactions = ledger_res.scalars().all()
    
    return {
        "user_id": wallet.user_id,
        "balance": wallet.balance,
        "frozen_amount": wallet.frozen_amount,
        "transactions": transactions
    }

@app.get("/api/admin/ledger")
async def get_all_ledger(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TransactionLedger).order_by(TransactionLedger.created_at.desc()).limit(50))
    return result.scalars().all()

@app.get("/api/admin/orders")
async def get_all_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PaymentOrder).order_by(PaymentOrder.created_at.desc()).limit(50))
    return result.scalars().all()
