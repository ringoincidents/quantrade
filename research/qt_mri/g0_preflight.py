"""QT-MRI G0 local data-package preflight. No downloads, no research authorization.
A structurally valid package is still NOT independently verified. No raw data
or private paths are emitted by the CLI. Research only.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

TRACKS={"BAA_LONG":("BAA10Y","2000-01-01","2025-12-31"),
        "HY_SHORT":("BAMLH0A0HYM2","2023-11-21","2025-12-31")}
MAX_BYTES=32*1024*1024
MAX_ROWS=100_000
REQUIRED={"VIXCLS","DGS10","SPY","QQQ"}
FIELDS={"release":("series_id","observation_date","value","first_public_at_utc","retrieved_at_utc","source_revision"),
        "price":("instrument","session_date","adjusted_close","close_at_utc","first_public_at_utc","retrieved_at_utc","source_revision")}

class Blocked(ValueError): pass
def need(ok,reason):
    if not ok: raise Blocked(reason)
def instant(x):
    try:
        d=datetime.fromisoformat(x.replace("Z","+00:00"))
        need(d.utcoffset() is not None,"NAIVE_TIME")
        return d.astimezone(timezone.utc)
    except (AttributeError,TypeError,ValueError) as e:
        if isinstance(e,Blocked):raise
        raise Blocked("INVALID_TIME") from None
def day(x):
    try:return date.fromisoformat(x)
    except (TypeError,ValueError):raise Blocked("INVALID_DATE") from None
def finite(x):
    try:v=float(x)
    except (TypeError,ValueError):raise Blocked("INVALID_VALUE") from None
    need(math.isfinite(v),"INVALID_VALUE")
    return v
def ref(x):return isinstance(x,str) and bool(x.strip()) and len(x)<=2048

def checked_bytes(root,name):
    need(isinstance(name,str) and Path(name).name==name and name.endswith(".csv"),"INVALID_FILE_NAME")
    p=root/name
    need(p.is_file() and not p.is_symlink(),"FILE_UNAVAILABLE")
    need(p.stat().st_size<=MAX_BYTES,"FILE_TOO_LARGE")
    with p.open("rb") as f:raw=f.read(MAX_BYTES+1)
    need(len(raw)<=MAX_BYTES,"FILE_TOO_LARGE")
    return raw

def inspect(root,manifest):
    need(isinstance(manifest,dict) and manifest.get("schema")=="qt-mri-g0-package-v1","INVALID_MANIFEST")
    track=manifest.get("track")
    need(isinstance(track,str) and track in TRACKS,"UNKNOWN_TRACK")
    credit,start,end=TRACKS[track]
    mode=manifest.get("mode")
    need(mode in ("SYNTHETIC","RESEARCH_CANDIDATE"),"INVALID_MODE")
    items=manifest.get("datasets")
    need(isinstance(items,list) and len(items)==5 and all(isinstance(x,dict) for x in items),"INVALID_DATASET_LIST")
    ids=[x.get("series_id") for x in items]
    need(all(isinstance(x,str) for x in ids) and len(set(ids))==5 and set(ids)==REQUIRED|{credit},"SERIES_SET_MISMATCH")
    files=[x.get("file") for x in items]
    need(all(isinstance(x,str) for x in files) and len(set(files))==5,"DUPLICATE_FILE")
    root=Path(root)
    results=[]
    for spec in items:
        sid=spec["series_id"];kind="price" if sid in ("SPY","QQQ") else "release"
        try:
            need(all(ref(spec.get(k)) for k in ("source_ref","rights_evidence_ref","availability_evidence_ref","revision_evidence_ref")),"MISSING_SOURCE_EVIDENCE")
            if kind=="price":
                need(spec.get("price_basis")=="DISTRIBUTION_AND_SPLIT_ADJUSTED","PRICE_BASIS_UNVERIFIED")
                need(ref(spec.get("calendar_evidence_ref")) and ref(spec.get("adjustment_evidence_ref")),"PRICE_EVIDENCE_MISSING")
            else:
                expected="INDEX_POINTS" if sid=="VIXCLS" else "PERCENT_POINTS"
                need(spec.get("unit")==expected,"UNIT_MISMATCH")
            raw=checked_bytes(root,spec.get("file"))
            need(hashlib.sha256(raw).hexdigest()==spec.get("sha256"),"HASH_MISMATCH")
            reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig"),newline=""))
            need(tuple(reader.fieldnames or ())==FIELDS[kind],"SCHEMA_MISMATCH")
            dates=set();previous=None;first=None;last=None;count=0
            for row in reader:
                count+=1
                need(count<=MAX_ROWS,"ROW_LIMIT")
                need(None not in row and all(v is not None for v in row.values()),"MALFORMED_ROW")
                key="instrument" if kind=="price" else "series_id"
                need(row[key]==sid,"SERIES_MISMATCH")
                dt=day(row["session_date" if kind=="price" else "observation_date"])
                known=instant(row["first_public_at_utc"]);retrieved=instant(row["retrieved_at_utc"])
                need(known<=retrieved,"RETRIEVED_BEFORE_PUBLICATION")
                need(ref(row["source_revision"]),"MISSING_REVISION")
                need(dt not in dates,"DUPLICATE_OBSERVATION")
                need(previous is None or dt>previous,"UNSORTED_OBSERVATIONS")
                # Delayed revisions cannot be silently substituted for first-known values.
                need(spec.get("revision_policy")=="FIRST_KNOWN_ONLY","REVISION_POLICY_UNVERIFIED")
                if kind=="price":
                    close=instant(row["close_at_utc"])
                    from zoneinfo import ZoneInfo
                    need(close.astimezone(ZoneInfo("America/New_York")).date()==dt,"SESSION_DATE_MISMATCH")
                    need(close<=known,"PRICE_BEFORE_CLOSE")
                    need(finite(row["adjusted_close"])>0,"INVALID_PRICE")
                else:
                    # UTC date can differ from observation date; reject clearly impossible dates.
                    need(known.date()>=dt,"RELEASE_BEFORE_OBSERVATION")
                    v=finite(row["value"])
                    need(sid!="VIXCLS" or v>=0,"INVALID_VIX")
                dates.add(dt);previous=dt;first=dt if first is None else first;last=dt
            need(count>0,"EMPTY_DATASET")
            # Coarse endpoint and count check only: exact calendar continuity is a separate review.
            if mode=="RESEARCH_CANDIDATE":
                lo,hi=day(start),day(end)
                need(first<=lo+timedelta(days=7) and last>=hi-timedelta(days=7),"COVERAGE_INSUFFICIENT")
                need(sum(lo<=x<=hi for x in dates)>=int((hi-lo).days*0.60),"DENSITY_INSUFFICIENT")
            results.append({"series_id":sid,"state":"STRUCTURE_OK","rows":count,"first_date":first.isoformat(),"last_date":last.isoformat()})
        except (Blocked,UnicodeError,csv.Error,OSError) as e:
            results.append({"series_id":sid,"state":"BLOCKED","reason":str(e) if isinstance(e,Blocked) else "FILE_OR_PARSE_ERROR"})
    return {"schema":"qt-mri-g0-preflight-v1","track":track,"mode":mode,"datasets":results,
        "structure_state":"STRUCTURE_OK" if all(x["state"]=="STRUCTURE_OK" for x in results) else "BLOCKED",
        "g0":"BLOCKED","g1_authorized":False,"prediction_authorized":False,
        "remaining_review":["SOURCE_RIGHTS_AND_EVIDENCE_AUTHENTICITY","FIRST_PUBLICATION_AND_VINTAGE_ATTESTATION","EXACT_SESSION_COVERAGE_AND_ADJUSTMENTS","SEALED_SPLIT_AND_EXECUTABLE_EVALUATION"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",required=True)
    p.add_argument("--manifest",required=True)
    a=p.parse_args()
    try:
        m=Path(a.manifest)
        need(m.is_file() and not m.is_symlink() and m.stat().st_size<=128*1024,"MANIFEST_UNAVAILABLE")
        with m.open("rb") as f: raw=f.read(128*1024+1)
        need(len(raw)<=128*1024,"MANIFEST_TOO_LARGE")
        result=inspect(a.directory,json.loads(raw))
    except (Blocked,OSError,UnicodeError,ValueError,TypeError) as e:
        result={"structure_state":"BLOCKED","g0":"BLOCKED","g1_authorized":False,"reason":str(e) if isinstance(e,Blocked) else "INVALID_MANIFEST"}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["structure_state"]=="STRUCTURE_OK" else 1

if __name__=="__main__":raise SystemExit(main())
