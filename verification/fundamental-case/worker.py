"""Private, one fixed public filing work order per process; no model or orders."""
import json,os,socket,threading
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from case_pilot import Transport,analyze,KEYS,DartFundamentalObservationProvider,DartProviderConfig,FundamentalQuery
from research_link import Verifier,PATH,PORT,mac,response_message,validate

class Work:
    def __init__(self):
        self.result={"state":"PENDING"}
        self.lock=threading.Lock()
    def run(self):
        key=os.getenv("DART_API_KEY")
        t=Transport()
        try:
            if not key:raise ValueError("MISSING_KEY")
            now=datetime.now(timezone.utc)
            p=DartFundamentalObservationProvider(api_key=key,transport=t,config=DartProviderConfig(statement_scope="CFS",allow_ofs_fallback=False,max_list_pages=4,report_codes=("11011",)),now=lambda:now,corp_code_overrides={"005930":"00126380"})
            r=analyze(p.query(FundamentalQuery(asset_id="KRX:005930",as_of=now.isoformat(),metric_keys=tuple(KEYS.values()),fiscal_period_end_from="2025-12-31",fiscal_period_end_to="2025-12-31")).observations)
            r["observed_at"]=datetime.now(timezone.utc).isoformat()
            validate(r)
        except Exception:
            r={"state":"BLOCKED"}
        with self.lock:self.result=r
        print("RESEARCH_WORK",r["state"],"requests",t.calls,flush=True)

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(5)
    def log_message(self,*args):pass
    def reply(self,status,body=b"",sig=None):
        self.send_response(status);self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(body)))
        if sig:self.send_header("X-QT-Response-Signature",sig)
        self.end_headers()
        if body:self.wfile.write(body)
    def single(self,k):
        v=self.headers.get_all(k) or [];return v[0] if len(v)==1 else ""
    def do_GET(self):
        if self.path=="/health":return self.reply(200,b'{"alive":true}')
        if self.path!=PATH:return self.reply(404)
        stamp,nonce,sig=[self.single(k) for k in ("X-QT-Time","X-QT-Nonce","X-QT-Signature")]
        if not self.server.verifier.verify(stamp,nonce,sig):return self.reply(403)
        with self.server.work.lock:r=self.server.work.result
        if r["state"]!="REPORT_READY":return self.reply(503)
        try:validate(r)
        except (ValueError,TypeError,KeyError):return self.reply(503)
        body=json.dumps(r,sort_keys=True,separators=(",",":")).encode()
        self.reply(200,body,mac(self.server.verifier.key,response_message(stamp,nonce,body)))
        print("RESEARCH_HANDOFF signed report served",flush=True)
    def do_POST(self):self.reply(405)

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,key,work):
        super().__init__(address,Handler);self.verifier=Verifier(key);self.work=work

class PrivateServer(Server):
    address_family=socket.AF_INET6

if __name__=="__main__":
    key=os.getenv("OFFICE_RESEARCH_LINK_KEY","")
    work=Work()
    server=PrivateServer(("::",PORT),key,work)
    if server.verifier.key:
        threading.Thread(target=work.run,daemon=True).start()
    print("RESEARCH_SERVER","READY" if server.verifier.key else "LOCKED",flush=True)
    server.serve_forever()
