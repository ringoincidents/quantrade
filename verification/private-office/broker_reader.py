"""Prepared TLS-only Toss REST reader; deliberately not wired to any runtime route.

Only one owner should instantiate this reader for a given Toss client. Never log
transport exceptions, credentials, tokens, account IDs or payloads.
"""
import json
import re
import ssl
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit, unquote
import urllib3

from portfolio_projection import ALLOWED, collect, Blocked

BASE="https://openapi.tossinvest.com"
EGRESS_URL="https://api.ipify.org"
EXPECTED_IP="141.164.41.178"
MAX_BYTES=2_000_000
TOKEN_COOLDOWN=60
MAX_REFRESH_SECONDS=120
TOKEN_PATTERN=re.compile(r"[!-~]{1,16384}")

class TransportFailure(Blocked):
    pass

class HTTPStatus(TransportFailure):
    def __init__(self,status):
        self.status=status
        super().__init__("BROKER_HTTP_"+str(status))

def proxy_parts(url):
    """A plain HTTP CONNECT proxy is never an accepted production transport."""
    try:
        p=urlsplit(url)
        if p.scheme!="https":
            raise TransportFailure("TLS_PROXY_REQUIRED")
        if not p.hostname or not p.port or not p.username or not p.password or p.path not in ("","/") or p.query or p.fragment:
            raise TransportFailure("PROXY_CONFIGURATION_INVALID")
        if not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}",p.hostname):
            raise TransportFailure("PROXY_CONFIGURATION_INVALID")
        user,password=unquote(p.username),unquote(p.password)
        if not all(re.fullmatch(r"[!-~]{1,256}",x) for x in (user,password)) or ":" in user:
            raise TransportFailure("PROXY_CONFIGURATION_INVALID")
        return "https://"+p.hostname+":"+str(p.port),user,password
    except TransportFailure:
        raise
    except (TypeError,ValueError,AttributeError):
        raise TransportFailure("PROXY_CONFIGURATION_INVALID") from None

def strict_json(raw):
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj:
                raise ValueError("duplicate JSON key")
            obj[k]=v
        return obj
    def invalid_constant(_):
        raise ValueError("nonfinite JSON")
    return json.loads(raw,parse_float=Decimal,parse_constant=invalid_constant,object_pairs_hook=pairs)

class TLSProxyTransport:
    def __init__(self,proxy_url,manager_factory=urllib3.ProxyManager):
        endpoint,user,password=proxy_parts(proxy_url)
        proxy_context=ssl.create_default_context()
        target_context=ssl.create_default_context()
        for context in (proxy_context,target_context):
            context.minimum_version=ssl.TLSVersion.TLSv1_2
        self.pool=manager_factory(endpoint,proxy_headers=urllib3.make_headers(proxy_basic_auth=user+":"+password),
                                  proxy_ssl_context=proxy_context,ssl_context=target_context,
                                  cert_reqs=ssl.CERT_REQUIRED,use_forwarding_for_https=False,
                                  num_pools=2,maxsize=1,block=True)
    def request(self,method,path,*,headers=None,fields=None):
        if method=="GET" and path=="EGRESS":
            url=EGRESS_URL
        elif (method=="GET" and path in ALLOWED) or (method=="POST" and path=="/oauth2/token"):
            url=BASE+path
        else:
            raise TransportFailure("METHOD_NOT_ALLOWED")
        outgoing={"Accept":"application/json","Accept-Encoding":"identity"}
        outgoing.update(headers or {})
        res=None
        try:
            opts=dict(headers=outgoing,redirect=False,retries=False,preload_content=False,
                      timeout=urllib3.Timeout(connect=4,read=5),pool_timeout=2)
            if method=="POST":
                from urllib.parse import urlencode
                opts["body"]=urlencode(fields or {}).encode("ascii")
                outgoing["Content-Type"]="application/x-www-form-urlencoded"
            elif fields is not None:
                opts["fields"]=fields
            res=self.pool.request(method,url,**opts)
            if res.status!=200:
                raise HTTPStatus(res.status)
            if res.headers.get("Content-Encoding","identity").lower()!="identity":
                raise TransportFailure("UNEXPECTED_CONTENT_ENCODING")
            raw=res.read(MAX_BYTES+1,decode_content=False)
            if len(raw)>MAX_BYTES:
                raise TransportFailure("RESPONSE_TOO_LARGE")
            if path=="EGRESS":
                return raw.decode("ascii").strip()
            return strict_json(raw)
        except TransportFailure:
            raise
        except (urllib3.exceptions.HTTPError,OSError,ValueError,TypeError,UnicodeError,RecursionError):
            raise TransportFailure("TRANSPORT_OR_PARSE_ERROR") from None
        finally:
            if res is not None:
                res.close()
                res.release_conn()
    def close(self):
        self.pool.clear()

class BrokerReader:
    """One serialized refresh lane; tokens are private, memory-only.

    No network occurs on construction. No retry of token POST or failed GET.
    A lost or invalid token is handled by a later explicit refresh, not a loop.
    Separate processes/legacy jobs must be disabled before real activation.
    """
    def __init__(self,transport,client_id,client_secret,*,clock=time.monotonic,
                 wall=lambda:datetime.now(timezone.utc)):
        if not all(isinstance(v,str) and v and len(v)<=4096 for v in (client_id,client_secret)):
            raise Blocked("CREDENTIALS_MISSING")
        self.transport=transport
        self.client_id=client_id
        self.client_secret=client_secret
        self.clock=clock
        self.wall=wall
        self.lock=threading.Lock()
        self.token=None
        self.expiry=0
        self.next_issue=0
        self.deadline=0
        self.fatal=None

    def _request(self,*a,**kw):
        if self.clock()>=self.deadline:
            raise Blocked("REFRESH_DEADLINE")
        result=self.transport.request(*a,**kw)
        if self.clock()>=self.deadline:
            raise Blocked("REFRESH_DEADLINE")
        return result

    def _ensure_token(self):
        now=self.clock()
        if self.token and now<self.expiry:
            return
        self.token=None
        if now<self.next_issue:
            raise Blocked("TOKEN_ISSUE_COOLDOWN")
        self.next_issue=now+TOKEN_COOLDOWN
        # Set cooldown before I/O; ambiguous token issuance is not retried.
        auth=self._request("POST","/oauth2/token",fields={
            "grant_type":"client_credentials","client_id":self.client_id,"client_secret":self.client_secret})
        if not isinstance(auth,dict) or auth.get("token_type","").lower()!="bearer":
            raise Blocked("TOKEN_SCHEMA_INVALID")
        token=auth.get("access_token")
        ttl=auth.get("expires_in")
        if not isinstance(token,str) or not TOKEN_PATTERN.fullmatch(token) or type(ttl) is not int or not 60<ttl<=604800:
            raise Blocked("TOKEN_SCHEMA_INVALID")
        self.expiry=now+ttl-60
        if self.clock()>=self.expiry:
            raise Blocked("TOKEN_EXPIRED")
        self.token=token

    def _read(self,path,account=None,params=None):
        if path not in ALLOWED:
            raise Blocked("METHOD_NOT_ALLOWED")
        if not self.token or self.clock()>=self.expiry:
            self.fatal="TOKEN_EXPIRED"
            raise Blocked(self.fatal)
        headers={"Authorization":"Bearer "+self.token}
        if account is not None:
            if not re.fullmatch(r"[0-9]{1,40}",account):
                raise Blocked("INVALID_ACCOUNT_ID")
            headers["X-Tossinvest-Account"]=account
        try:
            payload=self._request("GET",path,headers=headers,fields=params)
        except HTTPStatus as e:
            if e.status==401:
                self.token=None
                self.expiry=0
                self.next_issue=max(self.next_issue,self.clock()+TOKEN_COOLDOWN)
            if e.status in (401,403,429):
                self.fatal=str(e)
            raise
        if not isinstance(payload,dict) or "result" not in payload:
            raise Blocked("BROKER_SCHEMA_INVALID")
        return payload["result"]

    def refresh(self):
        if not self.lock.acquire(blocking=False):
            raise Blocked("REFRESH_BUSY")
        try:
            self.deadline=self.clock()+MAX_REFRESH_SECONDS
            self.fatal=None
            if self._request("GET","EGRESS")!=EXPECTED_IP:
                raise Blocked("EGRESS_MISMATCH")
            self._ensure_token()
            snapshot=collect(self._read,self.wall)
            if self.fatal:
                raise Blocked(self.fatal)
            if self.clock()>=self.deadline:
                raise Blocked("REFRESH_DEADLINE")
            return snapshot
        finally:
            self.lock.release()
