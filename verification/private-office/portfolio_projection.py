"""Read-only portfolio projection pilot. No transport, credentials, persistence or UI wiring.

Adapt existing Toss account-report read contract, not the legacy cash aggregation.
Inputs are sequential REST observations, not a broker-atomic snapshot.
"""
from datetime import datetime, timezone, timedelta
from decimal import Context, Decimal, localcontext
import re
import threading
import copy

MAX_ACCOUNTS=10
MAX_HOLDINGS=1000
MAX_WINDOW=timedelta(seconds=120)
MAX_AGE=timedelta(minutes=5)
ALLOWED={"/api/v1/accounts","/api/v1/holdings","/api/v1/buying-power","/api/v1/exchange-rate"}

class Blocked(ValueError):
    pass

def require(ok,code):
    if not ok:
        raise Blocked(code)

def number(value, *, nonnegative=False):
    if type(value) is int:
        value=str(value)
    if isinstance(value,str):
        require(re.fullmatch(r"-?\d{1,24}(\.\d{1,12})?",value) is not None,"INVALID_NUMBER")
        value=Decimal(value)
    require(isinstance(value,Decimal) and value.is_finite(),"INVALID_NUMBER")
    require(value.as_tuple().exponent>=-12 and value.adjusted()<24,"INVALID_NUMBER")
    require(not nonnegative or value>=0,"NEGATIVE_NUMBER")
    return value

def instant(value):
    require(isinstance(value,datetime) and value.utcoffset() is not None,"INVALID_TIME")
    return value.astimezone(timezone.utc)

def text(value,limit=120):
    require(isinstance(value,str) and 0<len(value)<=limit and all(c.isprintable() for c in value),"INVALID_TEXT")
    return value

def money(value,currency):
    require(isinstance(value,dict),"INVALID_MONEY")
    if "currency" in value:
        require(value["currency"]==currency,"CURRENCY_MISMATCH")
    return number(value.get("amount"),nonnegative=True)

def complete(payload):
    require(isinstance(payload,dict) and isinstance(payload.get("items"),list),"INVALID_HOLDINGS")
    require(payload.get("hasNext") in (None,False) and not payload.get("nextCursor"),"PAGINATION_UNVERIFIED")
    require(len(payload["items"])<=MAX_HOLDINGS,"HOLDINGS_LIMIT")
    return payload["items"]

def position(item):
    require(isinstance(item,dict),"INVALID_HOLDING")
    symbol=text(item.get("symbol"),40)
    currency=item.get("currency")
    require(currency in ("USD","KRW"),"CURRENCY_UNSUPPORTED")
    quantity=number(item.get("quantity"),nonnegative=True)
    last=number(item.get("lastPrice"),nonnegative=True)
    value=money(item.get("marketValue"),currency)
    average=item.get("averagePurchasePrice")
    pnl=item.get("profitLoss")
    result={"symbol":symbol,"name":text(item.get("name",symbol)),
            "currency":currency,"quantity":str(quantity),"last_price":str(last),
            "market_value":str(value),
            "average_purchase_price":None if average is None else str(number(average,nonnegative=True)),
            "unrealized_pnl":None,"unrealized_return_fraction":None}
    if pnl is not None:
        require(isinstance(pnl,dict),"INVALID_PNL")
        if "currency" in pnl:
            require(pnl["currency"]==currency,"CURRENCY_MISMATCH")
        if pnl.get("amount") is not None:
            result["unrealized_pnl"]=str(number(pnl["amount"]))
        if pnl.get("rate") is not None:
            result["unrealized_return_fraction"]=str(number(pnl["rate"]))
    return result

def collect(read,clock):
    """Injected GET-only reader(path, account=None, params=None).
    Returns no account identifiers, cash balances or fabricated total NAV.
    """
    started=instant(clock())
    def get(path,account=None,params=None):
        require(path in ALLOWED,"METHOD_NOT_ALLOWED")
        return read(path,account=account,params=params)
    accounts=get("/api/v1/accounts")
    require(isinstance(accounts,list) and 0<len(accounts)<=MAX_ACCOUNTS,"INVALID_ACCOUNTS")
    ids=[]
    for a in accounts:
        require(isinstance(a,dict),"INVALID_ACCOUNTS")
        seq=a.get("accountSeq")
        require(type(seq) in (str,int) and re.fullmatch(r"[0-9]{1,40}",str(seq)) is not None,"INVALID_ACCOUNT_ID")
        ids.append(str(seq))
    require(len(ids)==len(set(ids)),"DUPLICATE_ACCOUNT")
    output=[]
    for index,seq in enumerate(sorted(ids),1):
        holdings=[position(x) for x in complete(get("/api/v1/holdings",seq))]
        keys=[(x["symbol"],x["currency"]) for x in holdings]
        require(len(keys)==len(set(keys)),"DUPLICATE_HOLDING")
        power={}
        for currency in ("KRW","USD"):
            value=get("/api/v1/buying-power",seq,{"currency":currency})
            require(isinstance(value,dict),"INVALID_BUYING_POWER")
            if "currency" in value:
                require(value["currency"]==currency,"CURRENCY_MISMATCH")
            power[currency]=str(number(value.get("cashBuyingPower"),nonnegative=True))
        output.append({"snapshot_account_index":index,"holdings":holdings,"buying_power":power})
    fx=None
    fx_state="UNAVAILABLE"
    try:
        raw=get("/api/v1/exchange-rate",params={"baseCurrency":"USD","quoteCurrency":"KRW"})
        require(isinstance(raw,dict),"INVALID_FX")
        if "baseCurrency" in raw:
            require(raw["baseCurrency"]=="USD","INVALID_FX")
        if "quoteCurrency" in raw:
            require(raw["quoteCurrency"]=="KRW","INVALID_FX")
        fx=number(raw.get("rate"),nonnegative=True)
        require(fx>0,"INVALID_FX")
        fx_state="OBSERVED"
    except Exception:
        fx=None
    finished=instant(clock())
    require(started<=finished and finished-started<=MAX_WINDOW,"SNAPSHOT_WINDOW_INVALID")
    with localcontext(Context(prec=80)):
        total=Decimal(0)
        native={"KRW":Decimal(0),"USD":Decimal(0)}
        for a in output:
            for h in a["holdings"]:
                native[h["currency"]]+=number(h["market_value"])
        total=native["KRW"]+native["USD"]*fx if fx is not None else native["KRW"] if native["USD"]==0 else None
        for a in output:
            for h in a["holdings"]:
                v=number(h["market_value"])
                converted=v if h["currency"]=="KRW" else v*fx if fx is not None else None
                h["securities_weight_fraction"]=str(converted/total) if total is not None and total>0 and converted is not None else None
    return {"schema":"portfolio-observation-v1","source":"TOSS_REST",
            "qualification":"SEQUENTIAL_NOT_ATOMIC","started_at":started.isoformat(),"finished_at":finished.isoformat(),
            "accounts":output,"securities_native":{k:str(v) for k,v in native.items()},
            "securities_value_krw":None if total is None else str(total),
            "fx_usd_krw":None if fx is None else str(fx),"fx_state":fx_state,
            "cash_balance":None,"total_nav":None,"total_return":None,
            "decision_authorized":False,"order_authorized":False}

class SnapshotCache:
    """Event or disconnect invalidates, never applies a guessed trade delta.

    Only a completed REST refresh in the same generation can clear invalidation.
    Failed reads retain historical observation, explicitly not current.
    """
    def __init__(self):
        self.lock=threading.Lock()
        self.generation=0
        self.serial=0
        self.state="EMPTY"
        self.last=None
    def invalidate(self):
        with self.lock:
            self.generation+=1
            self.state="RECONCILIATION_REQUIRED"
    def begin(self):
        with self.lock:
            self.serial+=1
            self.state="REFRESHING"
            return self.generation,self.serial
    def finish(self,ticket,snapshot):
        with self.lock:
            if ticket!=(self.generation,self.serial):
                return False
            self.last=copy.deepcopy(snapshot)
            self.state="OBSERVED"
            return True
    def fail(self,ticket):
        with self.lock:
            if ticket==(self.generation,self.serial):
                self.state="REFRESH_FAILED"
    def view(self,now):
        now=instant(now)
        with self.lock:
            state=self.state
            if state=="OBSERVED" and self.last is not None:
                observed=instant(datetime.fromisoformat(self.last["finished_at"]))
                if not timedelta(0)<=now-observed<=MAX_AGE:
                    state="STALE"
            return {"state":state,"last_observation":copy.deepcopy(self.last),
                    "current_observation":state=="OBSERVED",
                    "decision_authorized":False,"order_authorized":False}
