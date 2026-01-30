from sqlalchemy import Column, String, Numeric, TIMESTAMP, func
import uuid
from database import Base

class UserWallet(Base):
    __tablename__ = "user_wallets"

    user_id = Column(String(255), primary_key=True)
    balance = Column(Numeric(18, 2), default=0.00, nullable=False)
    frozen_amount = Column(Numeric(18, 2), default=0.00, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    order_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=True)
    merchant_name = Column(String(255), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    status = Column(String(50), default='READY') # READY, COMPLETED, CANCELED
    created_at = Column(TIMESTAMP, server_default=func.now())

class TransactionLedger(Base):
    __tablename__ = "transaction_ledger"

    tx_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(String(255), nullable=True)
    type = Column(String(50), nullable=False) # BUY, PAY, REFUND
    amount = Column(Numeric(18, 2), nullable=False)
    related_id = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
