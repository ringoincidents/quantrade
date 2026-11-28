"""Research-only validation of caller-supplied provenance, not source certification."""
import re
import math
from datetime import datetime

def instant(value):
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.utcoffset() is None:
        raise ValueError("Timezone required")
    return dt

def quarter(value):
    if not re.fullmatch(r"[0-9]{4}Q[1-4]",value):
        raise ValueError("Invalid quarter")
    return int(value[:4])*4+int(value[-1])-1

def validate(rows):
    previous=None
    for row in rows:
        q=quarter(row["period"])
        if previous is not None and q!=previous+1:
            raise ValueError("Nonconsecutive or duplicate quarters")
        previous=q
        if row["unit"]!="REAL_GDP_QOQ_ANNUALIZED_PERCENT":
            raise ValueError("Unit mismatch")
        issued=instant(row["issued_at"])
        released=instant(row["actual_public_at"])
        if issued>=released:
            raise ValueError("Forecast must precede realization")
        if not re.fullmatch(r"[0-9a-f]{64}",row["source_sha256"]):
            raise ValueError("Source hash required")
        if row["vintage"]!="FIRST_RELEASE":
            raise ValueError("First release required")
        for k in ("actual","spf","iar"):
            if not math.isfinite(row[k]):
                raise ValueError("Nonfinite observation")
    for i,row in enumerate(rows):
        cutoff=instant(row["issued_at"])
        if any(instant(p["actual_public_at"])>cutoff for p in rows[:i]):
            raise ValueError("Training realization unavailable at forecast origin")
    return {k:[r[k] for r in rows] for k in ("actual","spf","iar")}
