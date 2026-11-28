import unittest,threading,http.client,json
from urllib.parse import urlencode
import ui_authenticated as u
import server as legacy
class AuthUI(unittest.TestCase):
    def setUp(self):
        self.host="test.up.railway.app";self.origin="https://"+self.host;self.token="a"*48
        self.server=u.Server(("127.0.0.1",0),legacy.Auth(self.token,self.origin))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.cookie=None
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,method="GET",body=None,extra=None):
        h={"Host":self.host}
        if self.cookie:h["Cookie"]=self.cookie
        h.update(extra or {})
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_address[1],timeout=10)
        try:
            c.request(method,path,body=body,headers=h);r=c.getresponse();return r.status,dict(r.getheaders()),r.read().decode()
        finally:c.close()
    def login(self):
        status,h,_=self.request("/login","POST",urlencode({"token":self.token}),{"Origin":self.origin,"Content-Type":"application/x-www-form-urlencoded"})
        self.assertEqual(status,303)
        self.assertIn("HttpOnly",h["Set-Cookie"])
        self.cookie=h["Set-Cookie"].split(";")[0]
    def test_unauthenticated(self):
        for path in ("/","/workspace?space=office","/legacy"):
            self.assertEqual(self.request(path)[0],303)
        for path in ("/workspace.js","/workspace/detail?path=%2Fassets","/workspace/detail?path=%2Finbox%2Flive","/api/portfolio"):
            self.assertEqual(self.request(path)[0],401)
    def test_authenticated_shell_and_preserved_legacy(self):
        self.login()
        for path in ("/","/workspace?space=lab","/workspace?space=office"):
            status,h,b=self.request(path)
            self.assertEqual(status,200);self.assertIn("인증 업무실",b)
            self.assertIn("script-src 'self'",h["Content-Security-Policy"])
            self.assertIn("no-store",h["Cache-Control"])
            self.assertIn("/workspace/detail",b)
            self.assertNotIn("기존 인증 업무실에서 열기",b)
        self.assertEqual(self.request("/workspace.js")[0],200)
        self.assertIn("투자 업무 대장",self.request("/legacy")[2])
        self.assertEqual(self.request("/assets")[0],200)
        self.assertEqual(self.request("/api/portfolio")[0],503)
    def test_detail_and_logout(self):
        self.login()
        for path in ("/assets","/performance","/lab","/reports","/records","/market/sources","date:2026-12-10"):
            status,h,b=self.request("/workspace/detail?"+urlencode({"path":path}))
            self.assertEqual(status,200,path);self.assertIn("title",json.loads(b))
            self.assertIn("no-store",h["Cache-Control"])
        self.assertEqual(self.request("/workspace/detail?path=%2Fapi%2Flink-check")[0],404)
        self.assertEqual(self.request("/workspace/detail?path=https%3A%2F%2Fexample.com")[0],404)
        self.assertEqual(self.request("/logout","POST","",{"Origin":self.origin})[0],303)
        self.assertEqual(self.request("/workspace/detail?path=%2Fperformance")[0],401)
    def test_host_origin_checks(self):
        self.assertEqual(self.request("/workspace",extra={"Host":"wrong.example"})[0],403)
        self.assertEqual(self.request("/login","POST",urlencode({"token":self.token}),{"Origin":"https://wrong.example","Content-Type":"application/x-www-form-urlencoded"})[0],403)
if __name__=="__main__":unittest.main()
