"""F-08 offline/manual workbench. No network, scheduler, broker or AI."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from .entry_monitor import Quote, Target, check_entry

SCHEMA = "entry-monitor-v1"
MARKETS = {"KRX": ("Asia/Seoul", "KRW"), "XNYS": ("America/New_York", "USD"),
           "XNAS": ("America/New_York", "USD")}
BASIS = "RAW_PER_SHARE"
ROOT = Path(__file__).resolve().parents[2]

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def instant(s):
    if not isinstance(s, str):
        raise ValueError("INVALID_TIME")
    d = datetime.fromisoformat(s)
    if d.utcoffset() is None:
        raise ValueError("INVALID_TIME")
    return d

def decimal(s):
    if not isinstance(s, str) or not re.fullmatch(r"-?\d{1,24}(\.\d{1,12})?", s):
        raise ValueError("INVALID_DECIMAL")
    return Decimal(s)

def text(s):
    if not isinstance(s, str) or not s.strip():
        raise ValueError("MISSING_PROVENANCE")
    return s

def market(instrument):
    m = re.fullmatch(r"(KRX|XNYS|XNAS):[A-Z0-9._-]{1,24}", instrument)
    if not m:
        raise ValueError("UNKNOWN_INSTRUMENT")
    return m[1]

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def evaluate(doc, *, manual_confirmed=False):
    require(doc["schema"] == SCHEMA, "UNKNOWN_SCHEMA")
    mode = doc["mode"]
    require(mode in ("SYNTHETIC", "MANUAL"), "UNSUPPORTED_MODE")
    require(mode != "MANUAL" or manual_confirmed, "MANUAL_CONFIRMATION_REQUIRED")
    now = instant(doc["as_of"])
    if mode == "MANUAL":
        require(now <= datetime.now(timezone.utc), "FUTURE_MANUAL_RUN")
    enabled = doc["enabled"]
    require(isinstance(enabled, list) and 0 < len(enabled) <= 100 and
            all(isinstance(i, str) for i in enabled) and len(set(enabled)) == len(enabled),
            "INVALID_ENABLED_LIST")
    for i in enabled:
        market(i)
    require(isinstance(doc["expected_sessions"],dict),"INVALID_SESSION_MAP")
    require(all(isinstance(doc[k], list) and all(isinstance(v, dict) for v in doc[k])
                for k in ("targets", "quotes", "approvals")), "INVALID_COLLECTION")
    revocations = doc.get("revocations", [])
    require(isinstance(revocations,list) and all(isinstance(r,dict) for r in revocations),"INVALID_REVOCATIONS")
    for r in revocations:
        text(r["ref"]); text(r["operator"]); text(r["target_hash"]); instant(r["revoked_at"])
    rows = []
    for instrument in enabled:
        row = dict(instrument=instrument, status="BLOCKED", reason=None, price=None,
                   currency=MARKETS[market(instrument)][1], entry_price=None,
                   gap=None, safety_margin=None, session_date=None, source=None,
                   target_version=None, expires_at=None, target_ref=None, quote_ref=None)
        try:
            m = market(instrument)
            zone, currency = MARKETS[m]
            session = doc["expected_sessions"][m]
            close = instant(session["close_at"])
            session_date = date.fromisoformat(session["session_date"])
            row["session_date"] = session_date.isoformat()
            require(close.astimezone(ZoneInfo(zone)).date() == session_date and close <= now,
                    "INVALID_EXPECTED_SESSION")
            candidates = [t for t in doc["targets"] if t.get("instrument") == instrument]
            require(candidates, "MISSING_TARGET")
            active = []
            for t in candidates:
                approved, expires = instant(t["approved_at"]), instant(t["expires_at"])
                require(approved < expires, "INVALID_TARGET_INTERVAL")
                invalid = instant(t["invalidated_at"]) if t.get("invalidated_at") is not None else None
                require(t["state"] in ("APPROVED", "REVOKED"), "INVALID_TARGET_STATE")
                revoked = any(r["target_hash"] == digest(t) and instant(r["revoked_at"]) <= now for r in revocations)
                if not revoked and t["state"] == "APPROVED" and approved <= now < expires and (invalid is None or invalid > now):
                    active.append(t)
            require(len(active) == 1, "DUPLICATE_APPROVAL" if active else "TARGET_NOT_CURRENT")
            t = active[0]
            row.update(target_version=text(t["version"]), expires_at=t["expires_at"], target_ref=digest(t))
            a = [a for a in doc["approvals"] if a.get("ref") == t["approval_ref"]]
            require(len(a) == 1 and a[0].get("target_hash") == digest(t)
                    and instant(a[0]["approved_at"]) == instant(t["approved_at"])
                    and bool(text(a[0]["operator"])), "APPROVAL_MISMATCH")
            require(t["currency"] == currency, "CURRENCY_MISMATCH")
            require(t["price_basis"] == BASIS, "PRICE_BASIS_MISMATCH")
            v, margin = decimal(t["value"]), decimal(t["margin"])
            require(v > 0 and 0 <= margin < 1, "INVALID_TARGET_VALUE")
            text(t["evidence"])
            with localcontext() as ctx:
                ctx.prec = 80
                row["entry_price"] = str(v * (1-margin))
            allq = [q for q in doc["quotes"] if q.get("instrument") == instrument]
            require(allq, "MISSING_QUOTE")
            current = [q for q in allq if q.get("session_date") == session_date.isoformat()]
            require(current, "SESSION_MISMATCH")
            require(all(type(q.get("revision")) is int and q["revision"] >= 1 for q in current),
                    "INVALID_REVISION")
            latest = max(q["revision"] for q in current)
            qs = [q for q in current if q["revision"] == latest]
            require(len(qs) == 1, "AMBIGUOUS_QUOTE")
            q = qs[0]
            row.update(quote_ref=digest(q), source=text(q["source"]))
            text(q["source_ref"])
            require(mode != "MANUAL" or q["source"] != "SYNTHETIC", "SYNTHETIC_QUOTE_IN_MANUAL_RUN")
            require(q["currency"] == currency, "CURRENCY_MISMATCH")
            require(q["price_basis"] == BASIS, "PRICE_BASIS_MISMATCH")
            require(q["finality"] == "FINAL", "QUOTE_NOT_FINAL")
            require(q["corporate_action_status"] == "CLEAR", "CORPORATE_ACTION_UNVERIFIED")
            require(instant(q["observed_at"]) == close, "CLOSE_TIME_MISMATCH")
            require(close <= instant(q["available_at"]) <= instant(q["retrieved_at"]) <= now,
                    "INVALID_AVAILABILITY")
            price = decimal(q["price"])
            require(price > 0, "INVALID_PRICE")
            row["price"] = str(price)
            # Session and finality are checked above; elapsed cutoff cannot reject a holiday/weekend.
            with localcontext() as ctx:
                ctx.prec = 80
                r = check_entry(Quote(instrument, price, currency, close, q["source"]),
                                Target(instrument, v, margin, currency, t["version"],
                                       t["evidence"], instant(t["approved_at"]), instant(t["expires_at"])),
                                as_of=now, max_age=now-close+timedelta(seconds=1))
                row.update({k: str(x) if isinstance(x, Decimal) else x for k, x in r.items()})
                if r["entry_price"] is not None:
                    row["gap"] = str((price-r["entry_price"])/r["entry_price"])
        except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError) as e:
            reason = str(e)
            row["reason"] = reason if re.fullmatch(r"[A-Z][A-Z_]+", reason) else "INVALID_INPUT"
        rows.append(row)
    rank = {"REVIEW":0, "BLOCKED":1, "WAIT":2}
    rows.sort(key=lambda r: (rank[r["status"]], Decimal(r["gap"] or "0"), r["instrument"]))
    return dict(schema=SCHEMA, run_id=digest(doc), mode=mode, as_of=doc["as_of"],
                expected_sessions=doc["expected_sessions"], rows=rows,
                data_health="INCOMPLETE" if any(r["status"]=="BLOCKED" for r in rows) else "DECLARED_COMPLETE",
                job_state="OFFLINE_COMPLETE")

def demo():
    session = {"session_date":"2026-11-27", "close_at":"2026-11-27T13:00:00-05:00"}
    d = dict(schema=SCHEMA, mode="SYNTHETIC", as_of="2026-11-28T08:00:00+09:00",
             expected_sessions={"XNYS":session}, enabled=[], targets=[], approvals=[], quotes=[], revocations=[])
    for symbol, price in (("DEMO_A","80"), ("DEMO_B","83.25"), ("DEMO_C",None)):
        i = "XNYS:"+symbol
        t = dict(instrument=i,currency="USD",value="100",margin="0.20",version="v1",
                 evidence="fictitious",approval_ref="approval-"+symbol,
                 approved_at="2026-11-26T12:00:00-05:00",expires_at="2026-12-31T00:00:00-05:00",
                 invalidated_at=None,price_basis=BASIS,state="APPROVED")
        d["enabled"].append(i)
        d["targets"].append(t)
        d["approvals"].append(dict(ref=t["approval_ref"],target_hash=digest(t),
                                   operator="SYNTHETIC",approved_at=t["approved_at"]))
        if price is not None:
            d["quotes"].append(dict(instrument=i,currency="USD",price=price,source="SYNTHETIC",
                source_ref="fixture",session_date=session["session_date"],observed_at=session["close_at"],
                retrieved_at="2026-11-27T13:10:00-05:00",available_at="2026-11-27T13:05:00-05:00",
                finality="FINAL",price_basis=BASIS,revision=1,corporate_action_status="CLEAR"))
    return d

def private_dir(path):
    p = Path(path).expanduser().resolve()
    require(p != ROOT and ROOT not in p.parents, "STORE_INSIDE_REPOSITORY")
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        require(p.stat().st_mode & 0o077 == 0, "STORE_NOT_PRIVATE")
    return p

def save_run(directory, doc, report, started):
    p = private_dir(directory)
    db = p/"runs.sqlite3"
    require(not db.is_symlink(), "UNSAFE_STORE")
    if db.exists() and os.name == "posix":
        require(db.stat().st_mode & 0o077 == 0, "STORE_NOT_PRIVATE")
    fd = os.open(db, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE IF NOT EXISTS inputs (kind TEXT, identity TEXT, hash TEXT, body TEXT, PRIMARY KEY(kind,identity))")
        con.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, input TEXT, report TEXT, started TEXT, finished TEXT)")
        # A previously observed revocation must never be silently omitted.
        current_revocations = {digest(r) for r in doc.get("revocations", [])}
        target_hashes = {digest(t) for t in doc["targets"]}
        for body, h in con.execute("SELECT body,hash FROM inputs WHERE kind=?",("revocation",)):
            r = json.loads(body)
            if r["target_hash"] in target_hashes:
                require(h in current_revocations,"MISSING_PRIOR_REVOCATION")
        # Store distinct versions, reject attempts to mutate a previously recorded input.
        for kind, records, keys in (("target",doc["targets"],("instrument","version")),
                                    ("quote",doc["quotes"],("instrument","session_date","revision")),
                                    ("approval",doc["approvals"],("ref",)),
                                    ("revocation",doc.get("revocations",[]),("ref",))):
            for item in records:
                if any(k not in item for k in keys):
                    continue
                identity = canonical([doc["mode"]]+[item[k] for k in keys])
                h = digest(item)
                old = con.execute("SELECT hash FROM inputs WHERE kind=? AND identity=?",(kind,identity)).fetchone()
                require(old is None or old[0] == h,"IMMUTABLE_INPUT_CONFLICT")
                con.execute("INSERT OR IGNORE INTO inputs VALUES (?,?,?,?)",(kind,identity,h,canonical(item)))
        con.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?)",
                    (report["run_id"],canonical(doc),canonical(report),started,utcnow()))
    return p

def atomic_write(path, contents):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def render(report):
    def e(v): return escape(str(v)) if v is not None else "—"
    def pct(v): return e(format(Decimal(v)*100,"+.2f")+"%") if v is not None else "—"
    labels = {"REVIEW":"검토","WAIT":"대기","BLOCKED":"보류"}
    out = []
    for r in report["rows"]:
        status = r["status"]
        out.append('<tr><th scope="row">'+e(r["instrument"])+'</th><td>'+e(r["price"])+' '+e(r["currency"])+'</td><td>'+e(r["entry_price"])+'</td><td>'+pct(r["gap"])+'</td><td class="'+status+'">'+labels[status]+'</td></tr>')
        out.append('<tr class="details"><td colspan="5"><details><summary>근거 · '+e(r["session_date"])+'</summary><p>사유: '+e(r["reason"])+'<br>출처: '+e(r["source"])+'<br>평가 버전: '+e(r["target_version"])+'<br>유효기간: '+e(r["expires_at"])+'</p></details></td></tr>')
    mode = "합성 데이터" if report["mode"]=="SYNTHETIC" else "수동 입력 · 검증되지 않은 시세"
    health = "일부 보류" if report["data_health"]=="INCOMPLETE" else "입력 검사 완료"
    return """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>QuanTrade — Field</title><style>
body{font:14px system-ui,sans-serif;background:#fafafa;color:#222;margin:0 auto;max-width:760px;padding:18px}header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #bbb;padding-bottom:12px}h1{font-size:20px;margin:0}h2{font-size:16px;margin:20px 0 8px}p,summary{font-size:12px;color:#555}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:9px 3px;border-bottom:1px solid #ddd}th:first-child,td:first-child{text-align:left}thead th{font-size:11px;color:#555}tbody th{font-size:12px;overflow-wrap:anywhere}.REVIEW{font-weight:700;color:#176748}.BLOCKED{color:#a05c00}.WAIT{color:#555}.details td{padding:3px 3px 9px;text-align:left}summary{cursor:pointer}.scroll{overflow-x:auto}@media(max-width:400px){body{padding:12px}th,td{font-size:11px}}</style><header><h1>QuanTrade / Field</h1><span>오프라인</span></header><h2>투자 기회 감시</h2><p>"""+e(mode)+" · "+e(health)+" · "+e(report["as_of"])+"""</p><div class="scroll"><table><thead><tr><th>종목</th><th>종가</th><th>검토가</th><th>괴리율</th><th>상태</th></tr></thead><tbody>"""+''.join(out)+"""</tbody></table></div><p>괴리율 = (종가 − 검토가) / 검토가. 검토는 매수 권고가 아님.</p></html>"""

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store",default="~/.quantrade-f08")
    sub = p.add_subparsers(dest="command",required=True)
    sub.add_parser("demo")
    init = sub.add_parser("template")
    run = sub.add_parser("run")
    run.add_argument("input")
    run.add_argument("--confirm-manual",action="store_true")
    approve = sub.add_parser("approve")
    approve.add_argument("input")
    approve.add_argument("instrument")
    approve.add_argument("version")
    approve.add_argument("--operator",required=True)
    approve.add_argument("--confirm-manual",action="store_true")
    view = sub.add_parser("show")
    view.add_argument("run_id")
    args = p.parse_args(argv)
    try:
        directory = private_dir(args.store)
        if args.command == "template":
            atomic_write(directory/"template.json",json.dumps(demo(),ensure_ascii=False,indent=2))
            print(directory/"template.json")
            return 0
        if args.command == "approve":
            require(args.confirm_manual,"MANUAL_CONFIRMATION_REQUIRED")
            doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
            require(doc["schema"] == SCHEMA and doc["mode"] == "MANUAL","MANUAL_INPUT_REQUIRED")
            targets = [t for t in doc["targets"] if t["instrument"]==args.instrument and t["version"]==args.version]
            require(len(targets)==1,"AMBIGUOUS_TARGET")
            t = targets[0]
            require(t["state"]=="APPROVED" and instant(t["approved_at"]) <= datetime.now(timezone.utc),"INVALID_APPROVAL")
            ref = text(t["approval_ref"])
            require(not any(a.get("ref")==ref for a in doc["approvals"]),"APPROVAL_ALREADY_EXISTS")
            doc["approvals"].append(dict(ref=ref,target_hash=digest(t),operator=text(args.operator),approved_at=t["approved_at"]))
            name = "approved-"+digest(doc)+".json"
            atomic_write(directory/name,json.dumps(doc,ensure_ascii=False,indent=2))
            print(directory/name)
            return 0
        if args.command == "show":
            require(re.fullmatch(r"[0-9a-f]{64}",args.run_id) is not None,"INVALID_RUN_ID")
            with sqlite3.connect(directory/"runs.sqlite3") as con:
                row = con.execute("SELECT report FROM runs WHERE id=?",(args.run_id,)).fetchone()
            require(row is not None,"UNKNOWN_RUN")
            report = json.loads(row[0])
        else:
            started = utcnow()
            doc = demo() if args.command=="demo" else json.loads(Path(args.input).read_text(encoding="utf-8"))
            report = evaluate(doc,manual_confirmed=getattr(args,"confirm_manual",False))
            save_run(directory,doc,report,started)
        name = "report-"+report["run_id"]
        atomic_write(directory/(name+".json"),json.dumps(report,ensure_ascii=False,indent=2))
        atomic_write(directory/(name+".html"),render(report))
        print(directory/(name+".html"))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as e:
        # Do not print private input content.
        reason = str(e) if re.fullmatch(r"[A-Z][A-Z_]+",str(e)) else type(e).__name__
        print("BLOCKED: "+reason)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
