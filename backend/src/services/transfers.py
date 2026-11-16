"""跨站调拨：预占、分批实搬、释放与站点台账。

并发与一致性约定：
- 状态迁移都用带条件的单条 UPDATE，由数据库行锁仲裁，成功者只可能有一个。
- 每批实搬在同一个事务里同时记调出与调入；任一步失败，两边都不变。
- 站点行按 id 升序加锁，避免相反方向的调拨互相死锁。
"""
import time

from fastapi import HTTPException
from sqlalchemy import case, select, update

from src.models import Job, Station, Transfer, TransferBatch

ACTIVE = ('reserved', 'partial')


def _now():
    return time.time()


def _lock_transfer(db, transfer_id):
    """先锁调拨单行，再锁站点行；所有写路径保持这个顺序，避免相反方向的死锁。"""
    return db.scalar(select(Transfer).where(Transfer.id == transfer_id).with_for_update())


def _lock_stations(db, names):
    """按 id 升序锁定涉及的站点行，返回 {name: Station}。"""
    rows = list(db.scalars(select(Station).where(Station.name.in_(sorted(set(names)))).order_by(Station.id).with_for_update()))
    return {s.name: s for s in rows}


def _station(db, name, locked=None):
    station = (locked or {}).get(name) or db.scalar(select(Station).where(Station.name == name))
    if not station:
        raise HTTPException(409, f'站点 {name} 台账缺失，请重新录入初始车数')
    return station


def _declared(data):
    declared = {}
    for item in data.stations:
        name = item.name.strip()
        if not name:
            raise HTTPException(422, '站点名称不能为空')
        if name in declared:
            raise HTTPException(422, f'站点 {name} 的初始车数重复录入')
        declared[name] = item.initial_bikes
    return declared


def create(db, data, user):
    job = db.get(Job, data.job_id)
    if not job or job.status != 'completed' or not job.approved:
        raise HTTPException(409, '调拨单必须引用已完成且获批准的研究结论')
    origin, destination = data.origin.strip(), data.destination.strip()
    if origin == destination:
        raise HTTPException(422, '调出站与调入站不能相同')
    declared = _declared(data)
    for name in (origin, destination):
        if name not in declared:
            raise HTTPException(422, f'须录入{name}的初始车数')
    existing = {s.name: s for s in db.scalars(
        select(Station).where(Station.name.in_(declared)).order_by(Station.id).with_for_update())}
    for name, initial in declared.items():
        station = existing.get(name)
        if not station:
            db.add(Station(name=name, initial_bikes=initial, moved_in=0, moved_out=0, reserved=0, created_at=_now()))
            continue
        if station.initial_bikes == initial:
            continue
        if station.moved_in or station.moved_out or station.reserved:
            raise HTTPException(409, f'{name} 初始车数已登记为 {station.initial_bikes}，台账有变动后不可改写')
        changed = db.execute(update(Station).where(
            Station.id == station.id, Station.moved_in == 0,
            Station.moved_out == 0, Station.reserved == 0
        ).values(initial_bikes=initial).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, f'{name} 初始车数已登记为 {station.initial_bikes}，与本次 {initial} 不一致')
    db.flush()
    transfer = Transfer(job_id=job.id, origin=origin, destination=destination, quantity=data.quantity,
                        moved_quantity=0, released_quantity=0, status='draft', initial_bikes=declared,
                        created_by=user.id, created_at=_now())
    db.add(transfer)
    db.flush()
    return transfer


def confirm(db, transfer_id):
    transfer = _lock_transfer(db, transfer_id)
    if not transfer:
        raise HTTPException(404, '调拨单不存在')
    if transfer.status != 'draft':
        raise HTTPException(409, '仅草稿状态的调拨单可以确认预占')
    origin = _station(db, transfer.origin)
    # 余车校验与预占在一条带条件的 UPDATE 里完成，并发确认只能有一个成功。
    reserved = db.execute(update(Station).where(
        Station.id == origin.id,
        Station.initial_bikes + Station.moved_in - Station.moved_out - Station.reserved >= transfer.quantity
    ).values(reserved=Station.reserved + transfer.quantity)
        .execution_options(synchronize_session=False))
    if reserved.rowcount != 1:
        raise HTTPException(409, f'{transfer.origin} 可用车不足，无法预占 {transfer.quantity} 辆')
    changed = db.execute(update(Transfer).where(Transfer.id == transfer_id, Transfer.status == 'draft')
                         .values(status='reserved', confirmed_at=_now())
                         .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise HTTPException(409, '仅草稿状态的调拨单可以确认预占')
    db.refresh(transfer)
    return transfer


def replay(db, transfer_id, batch_key, quantity, attempts=10):
    """同批号重试：只回读既有记账，不再变动任何车辆或预占。"""
    transfer = db.get(Transfer, transfer_id)
    if not transfer:
        raise HTTPException(404, '调拨单不存在')
    for attempt in range(attempts):
        batch = db.scalar(select(TransferBatch).where(
            TransferBatch.transfer_id == transfer_id, TransferBatch.batch_key == batch_key))
        if batch:
            if batch.quantity != quantity:
                raise HTTPException(409, f'批次 {batch_key} 已按 {batch.quantity} 辆记账，冲突回报已拒绝')
            return transfer, batch
        db.rollback()
        time.sleep(0.05)
        transfer = db.get(Transfer, transfer_id)
    raise HTTPException(409, '并发回报冲突，请刷新后重试')


def execute_batch(db, transfer_id, data, user):
    transfer = _lock_transfer(db, transfer_id)
    if not transfer:
        raise HTTPException(404, '调拨单不存在')
    existing = db.scalar(select(TransferBatch).where(
        TransferBatch.transfer_id == transfer_id, TransferBatch.batch_key == data.batch_key))
    if existing:
        if existing.quantity != data.quantity:
            raise HTTPException(409, f'批次 {data.batch_key} 已按 {existing.quantity} 辆记账，冲突回报已拒绝')
        return transfer, existing, True
    quantity, now = data.quantity, _now()
    # 先插入批次号：唯一约束是“同批只记一次”的最终仲裁。
    batch = TransferBatch(transfer_id=transfer_id, batch_key=data.batch_key, quantity=quantity,
                          created_by=user.id, created_at=now)
    db.add(batch)
    db.flush()
    # 锁定两站（先锁行），再在事务内同时增减。
    locked = _lock_stations(db, [transfer.origin, transfer.destination])
    origin = _station(db, transfer.origin, locked)
    destination = _station(db, transfer.destination, locked)
    changed = db.execute(update(Transfer).where(
        Transfer.id == transfer_id,
        Transfer.status.in_(ACTIVE),
        Transfer.quantity - Transfer.moved_quantity - Transfer.released_quantity >= quantity
    ).values(
        moved_quantity=Transfer.moved_quantity + quantity,
        status=case((Transfer.quantity == Transfer.moved_quantity + quantity, 'settled'), else_='partial'),
        settled_at=case((Transfer.quantity == Transfer.moved_quantity + quantity, now), else_=Transfer.settled_at)
    ).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.refresh(transfer)
        if transfer.status == 'settled':
            raise HTTPException(409, '调拨单已结清，晚到回报不恢复已释放的预占')
        if transfer.status == 'cancelled':
            raise HTTPException(409, '调拨单已取消，晚到回报不恢复已释放的预占')
        if transfer.status == 'draft':
            raise HTTPException(409, '调拨单尚未确认预占，不能回报实搬')
        raise HTTPException(409, '本批实搬数量超过未搬余量，冲突回报已拒绝')
    moved = db.execute(update(Station).where(
        Station.id == origin.id,
        Station.reserved >= quantity,
        Station.initial_bikes + Station.moved_in - Station.moved_out >= quantity
    ).values(reserved=Station.reserved - quantity, moved_out=Station.moved_out + quantity)
        .execution_options(synchronize_session=False))
    if moved.rowcount != 1:
        raise HTTPException(409, '调出站实际车辆不足，本批未记账')
    arrived = db.execute(update(Station).where(Station.id == destination.id)
                         .values(moved_in=Station.moved_in + quantity)
                         .execution_options(synchronize_session=False))
    if arrived.rowcount != 1:
        raise HTTPException(409, '调入站台账缺失，本批未记账')
    db.refresh(transfer)
    return transfer, batch, False


def cancel(db, transfer_id, attempts=3):
    """取消未搬部分。与回报竞态时以带条件的 UPDATE 定归属，失败重读后重试。"""
    for attempt in range(attempts):
        transfer = _lock_transfer(db, transfer_id)
        if not transfer:
            raise HTTPException(404, '调拨单不存在')
        if transfer.status == 'draft':
            changed = db.execute(update(Transfer).where(Transfer.id == transfer_id, Transfer.status == 'draft')
                                 .values(status='cancelled', released_quantity=Transfer.quantity)
                                 .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                db.rollback()
                continue
            db.refresh(transfer)
            return transfer
        if transfer.status not in ACTIVE:
            raise HTTPException(409, '调拨单已结清或已取消')
        moved, released_now = transfer.moved_quantity, transfer.released_quantity
        remaining = transfer.quantity - moved - released_now
        changed = db.execute(update(Transfer).where(
            Transfer.id == transfer_id,
            Transfer.status.in_(ACTIVE),
            Transfer.moved_quantity == moved,
            Transfer.released_quantity == released_now
        ).values(
            released_quantity=released_now + remaining,
            # 有实搬记录即为结清；一辆未搬则是取消。两者都不回滚已搬车辆。
            status=case((Transfer.moved_quantity > 0, 'settled'), else_='cancelled'),
            settled_at=case((Transfer.moved_quantity > 0, _now()), else_=Transfer.settled_at)
        ).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            db.rollback()
            continue
        origin = _station(db, transfer.origin)
        released = db.execute(update(Station).where(
            Station.id == origin.id, Station.reserved >= remaining
        ).values(reserved=Station.reserved - remaining)
            .execution_options(synchronize_session=False))
        if released.rowcount != 1:
            db.rollback()
            continue
        db.refresh(transfer)
        return transfer
    raise HTTPException(409, '调拨单正在被其他批次更新，请刷新后重试')
