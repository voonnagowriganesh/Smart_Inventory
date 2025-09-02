from datetime import datetime, timezone,date
import uuid
from uuid import uuid4
# ----------------------------
# Helpers
# ----------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _to_utc_datetime_from_date(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)

def _normalize_id(s: str) -> str:
    return s.strip()

def _gen_transaction_id() -> str:
    return f"txn-{uuid4().hex}"

def _gen_dispatch_id() -> str:
    return f"disp-{uuid4().hex}"
