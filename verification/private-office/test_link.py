import http.client
import threading
import unittest
import json
from unittest.mock import patch
from link_transport import check_link,Verifier,mac,request_message,PATH,FIXTURE
from link_gateway import Gateway

KEY="synthetic_fixture_only_abcdefghijklmnopqrstuvwxyz_1234567890"

class LinkTests(unittest.TestCase):
    def setUp(self):
        self.gateway=Gateway(("127.0.0.1",0),KEY)
        self.thread=threading.Thread(target=self.gateway.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.thread.join(2)
    def factory(self,host,port,timeout):
        self.assertEqual((host,port,timeout),("broker-gateway.railway.internal",8080,4))
        return http.client.HTTPConnection("127.0.0.1",self.gateway.server_port,timeout=timeout)
    def test_loopback_authenticated_response(self):
        self.assertEqual(check_link(KEY,connection_factory=self.factory),{"state":"SYNTHETIC_LINK_VERIFIED","real_data":False})
        self.assertEqual(check_link("x"*48,connection_factory=self.factory)["state"],"GATEWAY_REJECTED")
        self.assertEqual(check_link("",connection_factory=self.factory)["state"],"LINK_KEY_NOT_CONFIGURED")
    def test_replay_expiry_and_invalid_signature(self):
        v=Verifier(KEY,lambda:1000)
        key=KEY.encode(); nonce="a"*32; stamp="1000"
        sig=mac(key,request_message(stamp,nonce))
        self.assertEqual(v.verify(stamp,nonce,"b"*64),"INVALID_AUTH")
        self.assertEqual(v.verify(stamp,nonce,sig),"PASS")
        self.assertEqual(v.verify(stamp,nonce,sig),"REPLAY")
        self.assertEqual(v.verify("900","c"*32,mac(key,request_message("900","c"*32))),"EXPIRED_REQUEST")
    def test_gateway_no_mutation_and_unauthorized(self):
        c=self.factory("broker-gateway.railway.internal",8080,4)
        try:
            c.request("GET",PATH)
            r=c.getresponse(); self.assertEqual(r.status,403);r.read()
            c.request("POST",PATH)
            r=c.getresponse(); self.assertEqual(r.status,405);r.read()
            c.request("GET","/api/v1/accounts")
            r=c.getresponse(); self.assertEqual(r.status,404);r.read()
        finally:
            c.close()
    def test_reject_unsigned_or_tampered_response(self):
        from unittest.mock import MagicMock
        c=MagicMock();res=c.getresponse.return_value
        res.status=200;res.read.return_value=json.dumps(FIXTURE).encode()
        res.getheader.return_value="0"*64
        self.assertEqual(check_link(KEY,connection_factory=lambda *a,**kw:c)["state"],"INVALID_RESPONSE_AUTH")
