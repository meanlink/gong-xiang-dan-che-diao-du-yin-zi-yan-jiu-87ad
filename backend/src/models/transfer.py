from sqlalchemy import String, JSON, Double, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class Station(Base):
    """站点的共享车辆台账。

    actual  = 初始车数 + 累计调入 - 累计调出
    available = actual - 已预占
    """
    __tablename__ = 'stations'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    initial_bikes: Mapped[int] = mapped_column(Integer, default=0)
    moved_in: Mapped[int] = mapped_column(Integer, default=0)
    moved_out: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Double)


class Transfer(Base):
    """跨站调拨单：计划、预占、分批执行与释放都落库。"""
    __tablename__ = 'transfers'
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    origin: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer)
    moved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    released_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    initial_bikes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    confirmed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    settled_at: Mapped[float | None] = mapped_column(Double, nullable=True)


class TransferBatch(Base):
    """一次执行回报。同单同一批次号只能记账一次。"""
    __tablename__ = 'transfer_batches'
    __table_args__ = (UniqueConstraint('transfer_id', 'batch_key', name='uq_transfer_batch_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('transfers.id'))
    batch_key: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
