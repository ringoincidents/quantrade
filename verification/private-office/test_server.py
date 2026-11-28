import http.client
import json
import threading
import unittest
from urllib.parse import urlencode
from server import Auth,Server,TTL,MAX_ATTEMPTS

ORIGIN="https://fixture.up.railway.app"
HOST="fixture.up.railway.app"
# Explicit synthetic credential, never used as deployed configuration.
TOKEN="fixture_only_not_a_real_access_key_0000000000"

class AuthTests(unittest.TestCase):
    def test_locked_invalid_config(self):
        for a in (Auth("",ORIGIN),Auth(TOKEN,"http://fixture.up.railway.app"),Auth("short",ORIGIN)):
            self.assertFalse(a.ready)
            self.assertEqual(a.login(TOKEN),(503,None))
            self.assertFalse(a.active(TOKEN))

    def test_password_manager_punctuation_and_diagnostic(self):
        key="fixture-only!@#$%^&*()_+{}:<>?0123456789"
        a=Auth(key,ORIGIN)
        self.assertTrue(a.ready)
        self.assertEqual(a.configuration_reason,"READY")
        self.assertEqual(a.login(key)[0],303)
        for bad,reason in [("","ACCESS_KEY_MISSING"),("short","ACCESS_KEY_FORMAT_INVALID"),
                           (key+"\n","ACCESS_KEY_FORMAT_INVALID"),(key+" ","ACCESS_KEY_FORMAT_INVALID")]:
            self.assertEqual(Auth(bad,ORIGIN).configuration_reason,reason)
        self.assertEqual(Auth(key,"bad").configuration_reason,"ORIGIN_INVALID")
        self.assertFalse(Auth(key,"bad").ready)

    def test_expiry_logout_and_rate_limit(self):
        now=[1]
        a=Auth(TOKEN,ORIGIN,lambda:now[0])
        status,session=a.login(TOKEN)
        self.assertEqual(status,303)
        self.assertTrue(a.active(session))
        a.logout(session)
        self.assertFalse(a.active(session))
        _,session=a.login(TOKEN)
        now[0]+=TTL
        self.assertFalse(a.active(session))
        for _ in range(MAX_ATTEMPTS):
            self.assertEqual(a.login("wrong")[0],401)
        self.assertEqual(a.login(TOKEN)[0],429)
        now[0]+=61
        self.assertEqual(a.login(TOKEN)[0],303)

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.auth=Auth(TOKEN,ORIGIN)
        self.server=Server(("127.0.0.1",0),self.auth)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
    def request(self,method,path,body=None,headers=None):
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        h={"Host":HOST}
        h.update(headers or {})
        try:
            c.request(method,path,body=body,headers=h)
            r=c.getresponse()
            return r.status,dict(r.getheaders()),r.read()
        finally:
            c.close()
    def login(self,token=TOKEN,origin=ORIGIN):
        return self.request("POST","/login",urlencode({"token":token}),
                            {"Origin":origin,"Content-Type":"application/x-www-form-urlencoded"})
    def test_all_data_routes_require_auth(self):
        for path in ("/","/assets","/reports","/records"):
            status,h,_=self.request("GET",path)
            self.assertEqual((status,h["Location"]),(303,"/login"))
        self.assertEqual(self.request("GET","/api/status")[0],401)
        status,h,body=self.request("GET","/login")
        self.assertEqual(status,200)
        self.assertNotIn(TOKEN.encode(),body)
        self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("GET","/",headers={"Host":"evil.example"})[0],403)

    def test_login_session_logout_and_cookie_flags(self):
        self.assertEqual(self.login("wrong")[0],401)
        self.assertEqual(self.login(origin="https://evil.example")[0],403)
        status,h,body=self.login()
        self.assertEqual(status,303)
        cookie=h["Set-Cookie"]
        self.assertTrue(cookie.startswith("__Host-qt_session="))
        for flag in ("Path=/","Secure","HttpOnly","SameSite=Strict","Max-Age=1800"):
            self.assertIn(flag,cookie)
        self.assertNotIn(TOKEN,cookie)
        c=cookie.split(";")[0]
        for path in ("/","/assets","/reports","/records","/api/status"):
            status,h,body=self.request("GET",path,headers={"Cookie":c})
            self.assertEqual(status,200)
            self.assertNotIn(TOKEN.encode(),body)
            self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("GET","/api/status",headers={"Cookie":c+"; "+c})[0],401)
        self.assertEqual(self.request("POST","/logout",headers={"Cookie":c,"Origin":"https://evil.example"})[0],403)
        self.assertEqual(self.request("POST","/logout",headers={"Cookie":c,"Origin":ORIGIN})[0],303)
        self.assertEqual(self.request("GET","/api/status",headers={"Cookie":c})[0],401)

    def test_missing_configuration_is_fail_closed(self):
        self.server.auth=Auth("",ORIGIN)
        self.assertEqual(self.request("GET","/health")[0],200)
        for path in ("/","/login","/assets","/api/status"):
            self.assertEqual(self.request("GET",path)[0],503)
        self.assertEqual(self.login()[0],503)

    def test_portfolio_demo_auth_and_explicit_separation(self):
        self.assertEqual(self.request("GET","/api/portfolio")[0],401)
        self.assertEqual(self.request("GET","/api/demo/portfolio/initial")[0],401)
        self.assertEqual(self.request("GET","/assets/demo/initial")[0],303)
        status,h,_=self.login()
        c={"Cookie":h["Set-Cookie"].split(";")[0]}
        status,h,body=self.request("GET","/api/portfolio",headers=c)
        self.assertEqual(status,503)
        self.assertFalse(json.loads(body)["actual_account_connected"])
        self.assertNotIn(b"DEMO_KR",body)
        for name,state,total in [("initial","OBSERVED","660000"),("event","RECONCILIATION_REQUIRED","660000"),
                                 ("reconciled","OBSERVED","800000"),("failed","REFRESH_FAILED","660000"),("stale","STALE","660000")]:
            status,h,body=self.request("GET","/api/demo/portfolio/"+name,headers=c)
            self.assertEqual(status,200)
            v=json.loads(body)
            self.assertEqual(v["mode"],"SYNTHETIC_ONLY")
            self.assertEqual(v["state"],state)
            self.assertEqual(v["last_observation"]["securities_value_krw"],total)
            self.assertFalse(v["actual_account_connected"])
            self.assertFalse(v["order_authorized"])
            self.assertEqual(v["current_observation"],state=="OBSERVED")
            status,h,body=self.request("GET","/assets/demo/"+name,headers=c)
            self.assertEqual(status,200)
            self.assertIn("합성 데이터 / 실제 계좌 아님".encode(),body)
            self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("GET","/assets/demo/unknown",headers=c)[0],404)
        self.assertEqual(self.request("POST","/api/demo/portfolio/initial",headers={**c,"Origin":ORIGIN})[0],405)

    def test_f08_demo_auth_and_statuses(self):
        for path in ("/api/report","/api/demo/report/baseline"):
            self.assertEqual(self.request("GET",path)[0],401)
        self.assertEqual(self.request("GET","/reports/demo/baseline")[0],303)
        status,h,_=self.login()
        c={"Cookie":h["Set-Cookie"].split(";")[0]}
        status,h,body=self.request("GET","/api/report",headers=c)
        self.assertEqual(status,503)
        self.assertFalse(json.loads(body)["actual_data_connected"])
        for scenario,expected in [("baseline",["REVIEW","BLOCKED","WAIT"]),
                                  ("revised",["BLOCKED","WAIT","WAIT"]),
                                  ("revoked",["BLOCKED","BLOCKED","WAIT"]),
                                  ("expired",["BLOCKED","BLOCKED","BLOCKED"])]:
            status,h,body=self.request("GET","/api/demo/report/"+scenario,headers=c)
            self.assertEqual(status,200)
            data=json.loads(body)
            self.assertEqual(data["mode"],"SYNTHETIC_ONLY")
            self.assertFalse(data["decision_authorized"])
            self.assertFalse(data["order_authorized"])
            self.assertEqual([x["status"] for x in data["report"]["rows"]],expected)
            self.assertEqual(data["workbench_revision"],"f64b61c088a8e17cb04617f95d4f458671bea602")
            status,h,body=self.request("GET","/reports/demo/"+scenario,headers=c)
            self.assertEqual(status,200)
            self.assertIn("합성 데이터 / 실제 매수 신호 아님".encode(),body)
            self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("GET","/reports/demo/unknown",headers=c)[0],404)
        self.assertEqual(self.request("POST","/api/demo/report/baseline",headers={**c,"Origin":ORIGIN})[0],405)

    def test_link_check_requires_login(self):
        from unittest.mock import patch
        with patch("server.check_link",return_value={"state":"SYNTHETIC_LINK_VERIFIED","real_data":False}) as check:
            self.assertEqual(self.request("GET","/api/link-check")[0],401)
            check.assert_not_called()
            status,h,_=self.login()
            c={"Cookie":h["Set-Cookie"].split(";")[0]}
            status,h,body=self.request("GET","/api/link-check",headers=c)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)["state"],"SYNTHETIC_LINK_VERIFIED")
            self.assertEqual(h["Cache-Control"],"no-store, private")
            check.assert_called_once()

    def test_same_origin_form_policy_and_cross_origin_rejection(self):
        status,h,_=self.request("GET","/login")
        self.assertEqual(status,200)
        self.assertEqual(h["Referrer-Policy"],"same-origin")
        self.assertEqual(self.login(origin="null")[0],403)
        self.assertEqual(self.request("POST","/login",urlencode({"token":TOKEN}),{"Content-Type":"application/x-www-form-urlencoded"})[0],403)
        self.assertEqual(self.login(origin="https://evil.example")[0],403)
        self.assertEqual(self.login()[0],303)

    def test_no_mutations_or_oversized_login(self):
        status,h,_=self.login()
        c=h["Set-Cookie"].split(";")[0]
        self.assertEqual(self.request("POST","/api/status",headers={"Cookie":c,"Origin":ORIGIN})[0],405)
        self.assertEqual(self.request("POST","/login","x"*513,{"Origin":ORIGIN,"Content-Type":"application/x-www-form-urlencoded"})[0],400)

if __name__=="__main__":
    unittest.main()
