"""Read-only SYNTHETIC gateway link protocol. No broker calls or data."""
import hashlib
import hmac
import http.client
import json
import re
import secrets
import threading
import time

PATH="/internal/v1/link-check"
HOST="broker-gateway.railway.internal"
PORT=8080
LIMIT=4096
SKEW=30
MAX_NONCES=1024
HEX=re.compile(r"[0-9a-f]{64}")
NONCE=re.compile(r"[0-9a-f]{32}")
KEY=re.compile(r"[A-Za-z0-9_-]{48,128}")

def key_bytes(value):
    return value.encode("ascii") if isinstance(value,str) and KEY.fullmatch(value) else None

def mac(key, message):
    return hmac.new(key,message,hashlib.sha256).hexdigest()

def request_message(stamp,nonce):
    return ("qt-link-v1\nGET\n"+PATH+"\n"+stamp+"\n"+nonce).encode("ascii")

def response_message(stamp,nonce,body):
    return ("qt-response-v1\n"+stamp+"\n"+nonce+"\n"+hashlib.sha256(body).hexdigest()).encode("ascii")

FIXTURE={"protocol":"qt-link-v1","mode":"SYNTHETIC_ONLY","broker_connected":False,"order_authorized":False}

class Verifier:
    def __init__(self,key,clock=time.time):
        self.key=key_bytes(key)
        self.clock=clock
        self.used={}
        self.lock=threading.Lock()

    def verify(self,stamp,nonce,signature):
        if self.key is None:
            return "LINK_KEY_NOT_CONFIGURED"
        if not isinstance(stamp,str) or re.fullmatch(r"[0-9]{1,12}",stamp) is None or not NONCE.fullmatch(nonce or "") or not HEX.fullmatch(signature or ""):
            return "INVALID_AUTH"
        now=int(self.clock())
        if abs(now-int(stamp))>SKEW:
            return "EXPIRED_REQUEST"
        if not hmac.compare_digest(mac(self.key,request_message(stamp,nonce)),signature):
            return "INVALID_AUTH"
        with self.lock:
            self.used={k:v for k,v in self.used.items() if v>=now}
            if nonce in self.used:
                return "REPLAY"
            if len(self.used)>=MAX_NONCES:
                return "BUSY"
            self.used[nonce]=int(stamp)+SKEW
        return "PASS"

def check_link(key,*,connection_factory=http.client.HTTPConnection,clock=time.time):
    """Fixed destination, no caller-controlled URL, no redirects, status only."""
    key=key_bytes(key)
    if key is None:
        return {"state":"LINK_KEY_NOT_CONFIGURED","real_data":False}
    nonce=secrets.token_hex(16)
    stamp=str(int(clock()))
    conn=None
    try:
        conn=connection_factory(HOST,PORT,timeout=4)
        conn.request("GET",PATH,headers={"X-QT-Time":stamp,"X-QT-Nonce":nonce,
                     "X-QT-Signature":mac(key,request_message(stamp,nonce))})
        res=conn.getresponse()
        if res.status!=200:
            return {"state":"GATEWAY_REJECTED","real_data":False}
        body=res.read(LIMIT+1)
        if len(body)>LIMIT:
            return {"state":"RESPONSE_TOO_LARGE","real_data":False}
        sig=res.getheader("X-QT-Response-Signature","")
        if not HEX.fullmatch(sig) or not hmac.compare_digest(sig,mac(key,response_message(stamp,nonce,body))):
            return {"state":"INVALID_RESPONSE_AUTH","real_data":False}
        obj=json.loads(body)
        if obj!=FIXTURE:
            return {"state":"UNEXPECTED_RESPONSE","real_data":False}
        return {"state":"SYNTHETIC_LINK_VERIFIED","real_data":False}
    except (OSError,http.client.HTTPException,ValueError,TypeError):
        return {"state":"GATEWAY_UNAVAILABLE","real_data":False}
    finally:
        if conn is not None:
            conn.close()
