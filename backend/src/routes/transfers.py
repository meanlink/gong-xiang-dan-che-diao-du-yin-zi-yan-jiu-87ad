from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.config.database import get_db
from src.models import Station, Transfer, TransferBatch
from src.schemas.transfer import TransferInput, TransferBatchInput
from src.middlewares.auth import current_user, can_write
from src.services import transfers
from src.services.audit import record
from src.utils.serialization import station_dict, transfer_dict, batch_dict
router = APIRouter()


def _with_batches(db, transfer):
    batches = list(db.scalars(select(TransferBatch).where(TransferBatch.transfer_id == transfer.id).order_by(TransferBatch.id)))
    return transfer_dict(transfer, batches)


@router.get('/stations')
def stations(db=Depends(get_db), u=Depends(current_user)):
    return [station_dict(s) for s in db.scalars(select(Station).order_by(Station.id))]


@router.get('/transfers')
def listing(db=Depends(get_db), u=Depends(current_user)):
    rows = list(db.scalars(select(Transfer).order_by(Transfer.id.desc()).limit(100)))
    batches = {}
    if rows:
        for b in db.scalars(select(TransferBatch).where(TransferBatch.transfer_id.in_([t.id for t in rows])).order_by(TransferBatch.id)):
            batches.setdefault(b.transfer_id, []).append(b)
    return [transfer_dict(t, batches.get(t.id, [])) for t in rows]


@router.get('/transfers/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    t = db.get(Transfer, id)
    if not t:
        raise HTTPException(404, '调拨单不存在')
    return _with_batches(db, t)


@router.post('/transfers', status_code=201)
def create(data: TransferInput, db=Depends(get_db), u=Depends(can_write)):
    try:
        t = transfers.create(db, data, u)
        record(db, u.email, 'transfer.draft', {'id': t.id, 'origin': t.origin, 'destination': t.destination, 'quantity': t.quantity, 'job_id': t.job_id})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '站点或调拨单并发写入冲突，请刷新后重试')
    except HTTPException:
        db.rollback()
        raise
    db.refresh(t)
    return transfer_dict(t, [])


@router.post('/transfers/{id}/confirm')
def confirm(id: int, db=Depends(get_db), u=Depends(can_write)):
    try:
        t = transfers.confirm(db, id)
        record(db, u.email, 'transfer.reserve', {'id': id, 'origin': t.origin, 'quantity': t.quantity})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '并发确认冲突，请刷新后重试')
    except HTTPException:
        db.rollback()
        raise
    return _with_batches(db, t)


@router.post('/transfers/{id}/batches', status_code=201)
def execute(id: int, data: TransferBatchInput, db=Depends(get_db), u=Depends(can_write)):
    try:
        t, batch, replayed = transfers.execute_batch(db, id, data, u)
        if not replayed:
            record(db, u.email, 'transfer.batch', {'id': id, 'batch': batch.batch_key, 'quantity': batch.quantity})
        db.commit()
    except IntegrityError:
        db.rollback()
        t, batch = transfers.replay(db, id, data.batch_key, data.quantity)
        replayed = True
    except HTTPException:
        db.rollback()
        raise
    return {**_with_batches(db, t), 'batch': batch_dict(batch), 'replayed': replayed}


@router.post('/transfers/{id}/cancel')
def cancel(id: int, db=Depends(get_db), u=Depends(can_write)):
    try:
        t = transfers.cancel(db, id)
        record(db, u.email, 'transfer.cancel', {'id': id, 'released': t.released_quantity, 'status': t.status})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '并发取消冲突，请刷新后重试')
    except HTTPException:
        db.rollback()
        raise
    return _with_batches(db, t)
