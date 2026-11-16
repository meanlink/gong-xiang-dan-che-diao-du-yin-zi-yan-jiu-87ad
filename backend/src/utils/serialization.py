import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def station_dict(s):
    actual = s.initial_bikes + s.moved_in - s.moved_out
    return {'id':s.id, 'name':s.name, 'initial_bikes':s.initial_bikes, 'moved_in':s.moved_in,
            'moved_out':s.moved_out, 'reserved':s.reserved, 'actual':actual, 'available':actual - s.reserved}
def batch_dict(b):
    return {'id':b.id, 'batch_key':b.batch_key, 'quantity':b.quantity, 'created_by':b.created_by, 'created_at':b.created_at}
def transfer_dict(t, batches=None):
    remaining = t.quantity - t.moved_quantity - t.released_quantity
    return {**{k:getattr(t,k) for k in ['id','job_id','origin','destination','quantity','moved_quantity','released_quantity','status','initial_bikes','created_by','created_at','confirmed_at','settled_at']},
            'remaining': remaining, 'batches': [batch_dict(b) for b in (batches or [])]}
