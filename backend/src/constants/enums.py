from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class TransferStatus(str, Enum):
    draft = 'draft'
    reserved = 'reserved'
    partial = 'partial'
    settled = 'settled'
    cancelled = 'cancelled'
