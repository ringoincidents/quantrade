"""Private gateway link-check service. No external requests; no broker access."""
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from link_transport import Verifier,PATH,PORT,FIXTURE,mac,response_message

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self,*args):
        pass
    def reply(self,status,body=b"",sig=None):
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        if sig:
            self.send_header("X-QT-Response-Signature",sig)
        self.end_headers()
        if body:
            self.wfile.write(body)
    def single(self,name):
        v=self.headers.get_all(name) or []
        return v[0] if len(v)==1 else ""
    def do_GET(self):
        if self.path=="/health":
            self.reply(200,b'{"alive":true}')
            return
        if self.path!=PATH:
            self.reply(404)
            return
        stamp,nonce,sig=[self.single(n) for n in ("X-QT-Time","X-QT-Nonce","X-QT-Signature")]
        result=self.server.verifier.verify(stamp,nonce,sig)
        if result!="PASS":
            self.reply(503 if result in ("LINK_KEY_NOT_CONFIGURED","BUSY") else 403)
            return
        body=json.dumps(FIXTURE,sort_keys=True,separators=(",",":")).encode()
        self.reply(200,body,mac(self.server.verifier.key,response_message(stamp,nonce,body)))
    def do_POST(self):
        self.reply(405)

class Gateway(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,key):
        super().__init__(address,Handler)
        self.verifier=Verifier(key)

class PrivateGateway(Gateway):
    address_family=socket.AF_INET6

if __name__=="__main__":
    key=os.environ.get("OFFICE_BROKER_LINK_KEY","")
    server=PrivateGateway(("::",PORT),key)
    print(json.dumps({"mode":"SYNTHETIC_LINK_ONLY","configuration":"READY" if server.verifier.key else "LOCKED","broker_connected":False}),flush=True)
    server.serve_forever()
