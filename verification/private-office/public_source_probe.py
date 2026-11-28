"""One-shot public source compatibility probe; no secrets, no raw data output."""
from datetime import datetime,timezone
from calendar_refresh import fetch as bls_fetch,parse as bls_parse
from treasury_view import fetch,parse,ET
import json
now=datetime.now(timezone.utc)
def check(name,run):
    try:
        value=run()
        print(json.dumps({"source":name,"state":"PASS_SCHEMA",**value}))
    except Exception as e:
        print(json.dumps({"source":name,"state":"BLOCKED","error_type":type(e).__name__}))
def bls():
    rows=bls_parse(bls_fetch(),now)
    return {"events":len(rows)}
def rates():
    year=now.astimezone(ET).year
    raw,_=fetch(year)
    result=parse(raw,year,now)
    return {"observation_date":result["observation_date"],"two_y":result["ust_par_2y_pct"],"ten_y":result["ust_par_10y_pct"],"spread_bp":result["spread_10y_2y_bp"]}
check("BLS_ICS",bls);check("UST_PAR",rates)
