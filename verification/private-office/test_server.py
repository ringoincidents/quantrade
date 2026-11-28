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

    def test_macro_auth_and_no_mutation(self):
        for p in ("/api/macro/D","/api/macro/M"):self.assertEqual(self.request("GET",p)[0],401)
        self.assertEqual(self.request("GET","/market/macro/M")[0],303)
        _,h,_=self.login();c={"Cookie":h["Set-Cookie"].split(";")[0]}
        from unittest.mock import patch
        from macro_view import Cache
        cache=Cache(lambda g,n: (_ for _ in ()).throw(TimeoutError()))
        with patch("server.MACRO_CACHE",cache):
            for g in ("D","M"):
                st,h,b=self.request("GET","/api/macro/"+g,headers=c)
                self.assertEqual(st,200);v=json.loads(b);self.assertEqual(v["state"],"REFRESH_FAILED")
                self.assertTrue(v["historical_only"]);self.assertFalse(v["decision_authorized"])
                self.assertEqual(self.request("GET","/market/macro/"+g,headers=c)[0],200)
        self.assertEqual(self.request("POST","/api/macro/M",headers={**c,"Origin":ORIGIN})[0],405)

    def test_treasury_reference_route(self):
        self.assertEqual(self.request("GET","/api/treasury")[0],401)
        self.assertEqual(self.request("GET","/market/rates")[0],303)
        _,h,_=self.login();c={"Cookie":h["Set-Cookie"].split(";")[0]}
        from unittest.mock import patch
        from treasury_view import Cache
        from datetime import datetime,timezone
        cache=Cache(lambda y: (_ for _ in ()).throw(TimeoutError()),now=lambda:datetime(2026,11,28,tzinfo=timezone.utc))
        with patch("server.TREASURY_CACHE",cache):
            st,h,b=self.request("GET","/api/treasury",headers=c)
            self.assertEqual(st,200);self.assertEqual(h["Cache-Control"],"no-store, private")
            v=json.loads(b);self.assertEqual(v["state"],"REFRESH_FAILED");self.assertTrue(v["historical_only"])
            self.assertFalse(v["data"]["decision_authorized"])
            self.assertEqual(self.request("GET","/market/rates",headers=c)[0],200)
        self.assertEqual(self.request("POST","/api/treasury",headers={**c,"Origin":ORIGIN})[0],405)

    def test_new_surfaces_auth_and_boundaries(self):
        for p in ("/lab","/strategies","/inbox"):
            self.assertEqual(self.request("GET",p)[0],303)
        for p in ("/api/demo/lab/D","/api/demo/strategies","/api/inbox","/api/calendar-refresh"):
            self.assertEqual(self.request("GET",p)[0],401)
        _,h,_=self.login();c={"Cookie":h["Set-Cookie"].split(";")[0]}
        for f in ("D","W","M","Y"):
            st,h,b=self.request("GET","/api/demo/lab/"+f,headers=c)
            self.assertEqual(st,200);v=json.loads(b);self.assertEqual(v["mode"],"SYNTHETIC_ONLY")
            self.assertFalse(v["decision_authorized"]);self.assertFalse(v["actual_data_connected"])
            self.assertEqual(self.request("GET","/lab/"+f,headers=c)[0],200)
        self.assertEqual(self.request("GET","/lab/Z",headers=c)[0],404)
        st,h,b=self.request("GET","/api/demo/strategies",headers=c);self.assertEqual(st,200)
        self.assertFalse(json.loads(b)["actual_backtest"])
        self.assertEqual(self.request("GET","/strategies",headers=c)[0],200)
        st,h,b=self.request("GET","/api/inbox",headers=c);self.assertEqual(st,200)
        self.assertFalse(json.loads(b)["approval_authorized"])
        self.assertEqual(self.request("GET","/inbox",headers=c)[0],200)
        self.assertEqual(self.request("POST","/api/inbox",headers={**c,"Origin":ORIGIN})[0],405)
        from unittest.mock import patch
        with patch("server.BLS_CACHE.get",return_value={"state":"REFRESH_FAILED","events":[],"checked_at":None}):
            self.assertEqual(self.request("GET","/api/calendar-refresh",headers=c)[0],200)

    def test_market_room_dated_reference_and_auth(self):
        self.assertEqual(self.request("GET","/market")[0],303)
        self.assertEqual(self.request("GET","/api/market-room")[0],401)
        status,h,_=self.login()
        c={"Cookie":h["Set-Cookie"].split(";")[0]}
        status,h,body=self.request("GET","/api/market-room",headers=c)
        self.assertEqual(status,200)
        self.assertEqual(h["Cache-Control"],"no-store, private")
        v=json.loads(body)
        self.assertEqual(v["mode"],"DATED_OFFICIAL_REFERENCE")
        self.assertFalse(v["auto_refresh"])
        self.assertFalse(v["live_market_feed"])
        self.assertFalse(v["calendar"]["complete"])
        self.assertFalse(v["decision_authorized"])
        self.assertIsNone(v["market_regime"])
        self.assertEqual(v["calendar"]["events"][0]["at_kst"],"2026-12-02T00:00:00+09:00")
        self.assertEqual(v["calendar"]["events"][1]["at_kst"],"2026-12-04T22:30:00+09:00")
        self.assertEqual(v["calendar"]["events"][2]["at_kst"],"2026-12-10T04:00:00+09:00")
        sessions={x["date_et"]:x for x in v["exchange"]["sessions"]}
        self.assertEqual(sessions["2026-11-26"]["state"],"CLOSED_SCHEDULED")
        self.assertEqual(sessions["2026-11-27"]["close_kst"],"2026-11-28T03:00:00+09:00")
        self.assertFalse(v["exchange"]["actual_close_verified"])
        self.assertEqual(len(v["macro"]),5)
        self.assertEqual(self.request("GET","/api/market",headers=c)[0],503)
        from unittest.mock import patch
        with patch("server.BLS_CACHE.get",return_value={"state":"REFRESH_FAILED","events":[],"checked_at":None}):
            status,h,body=self.request("GET","/market",headers=c)
        self.assertEqual(status,200)
        for text in ("시장 상황실","자동 갱신 미연결","12월 주요 경제 발표 한국시간","미연결","합성 사례"):
            self.assertIn(text.encode(),body)
        self.assertEqual(self.request("POST","/api/market-room",headers={**c,"Origin":ORIGIN})[0],405)

    def test_market_research_auth_and_point_in_time(self):
        self.assertEqual(self.request("GET","/api/market")[0],401)
        self.assertEqual(self.request("GET","/api/demo/market/baseline")[0],401)
        self.assertEqual(self.request("GET","/market/demo/baseline")[0],303)
        status,h,_=self.login()
        c={"Cookie":h["Set-Cookie"].split(";")[0]}
        self.assertEqual(self.request("GET","/api/market",headers=c)[0],503)
        from unittest.mock import patch
        with patch("server.BLS_CACHE.get",return_value={"state":"REFRESH_FAILED","events":[],"checked_at":None}):
            self.assertEqual(self.request("GET","/market",headers=c)[0],200)
        for name in ("baseline","late-release","credit-missing","baa-proxy"):
            status,h,body=self.request("GET","/api/demo/market/"+name,headers=c)
            self.assertEqual(status,200)
            v=json.loads(body)
            self.assertEqual(v["g0"],"BLOCKED")
            for key in ("market_regime","composite_index","forecast"):
                self.assertIsNone(v[key])
            self.assertFalse(v["decision_authorized"])
            self.assertFalse(v["order_authorized"])
            self.assertEqual(v["fixture_day_260"]["vix_known"]["value"],20.0 if name=="late-release" else 35.0)
            if name=="credit-missing":
                self.assertIsNone(v["synthetic_events"]["combined"])
                self.assertEqual(v["coverage"]["credit"],0)
            elif name=="baa-proxy":
                self.assertEqual(v["credit_kind"],"INVESTMENT_GRADE_PROXY_NOT_HY")
            else:
                self.assertEqual(v["credit_series"],"BAMLH0A0HYM2")
            status,h,body=self.request("GET","/market/demo/"+name,headers=c)
            self.assertEqual(status,200)
            self.assertIn("합성 연구 / 실제 장세 판정 아님".encode(),body)
            self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("POST","/api/market",headers={**c,"Origin":ORIGIN})[0],405)

    def test_portfolio_risk_review_and_authority(self):
        for path in ("/api/risk","/api/demo/risk/baseline"):
            self.assertEqual(self.request("GET",path)[0],401)
        self.assertEqual(self.request("GET","/risk/demo/baseline")[0],303)
        status,h,_=self.login()
        c={"Cookie":h["Set-Cookie"].split(";")[0]}
        self.assertEqual(self.request("GET","/api/risk",headers=c)[0],503)
        self.assertEqual(self.request("GET","/risk",headers=c)[0],200)
        for name,expected,ceiling in [("baseline","PASS_WITH_LIMITS",2.5),("strong-alternative",None,None),
            ("no-cash",None,None),("correlation-veto","VETO",None),("missing-risk","REQUIRE_MORE_INFORMATION",None),
            ("sector-limit","PASS_WITH_LIMITS",0.0),("drawdown-veto","VETO",None)]:
            status,h,body=self.request("GET","/api/demo/risk/"+name,headers=c)
            self.assertEqual(status,200)
            v=json.loads(body)
            self.assertEqual(v["mode"],"SYNTHETIC_ONLY")
            self.assertEqual(v["risk"]["status"] if v["risk"] else None,expected)
            self.assertEqual(v["illustrative_incremental_ceiling_pct"],ceiling)
            self.assertIsNone(v["target_weight_pct"])
            self.assertFalse(v["policy_approved"])
            self.assertFalse(v["decision_authorized"])
            self.assertFalse(v["order_authorized"])
            self.assertEqual(v["portfolio"]["capital_headroom"]["deterministic_upper_bound_pct"],0.0 if name=="no-cash" else 5.0)
            status,h,body=self.request("GET","/risk/demo/"+name,headers=c)
            self.assertEqual(status,200)
            self.assertIn("합성 포트폴리오 / 실제 운용 기준 아님".encode(),body)
            self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("POST","/api/risk",headers={**c,"Origin":ORIGIN})[0],405)

    def test_case_register_auth_and_gates(self):
        self.assertEqual(self.request("GET","/api/demo/case/baseline")[0],401)
        self.assertEqual(self.request("GET","/cases/demo/baseline")[0],303)
        self.assertEqual(self.request("GET","/api/cases")[0],401)
        status,h,_=self.login()
        c={"Cookie":h["Set-Cookie"].split(";")[0]}
        self.assertEqual(self.request("GET","/api/cases",headers=c)[0],503)
        self.assertEqual(self.request("GET","/cases")[0],303)
        status,h,body=self.request("GET","/cases",headers=c)
        self.assertEqual(status,200)
        self.assertIn(b"/cases/demo/baseline",body)
        for name,ready in [("baseline",True),("missing",False),("invalid-domain",False),("counter-gap",True),("expired",True)]:
            status,h,body=self.request("GET","/api/demo/case/"+name,headers=c)
            self.assertEqual(status,200)
            obj=json.loads(body)
            self.assertEqual(obj["mode"],"SYNTHETIC_ONLY")
            self.assertEqual(obj["valuation"] is not None,ready)
            self.assertEqual(obj["method_gate"]["status"],"READY" if ready else "NOT_APPLICABLE")
            self.assertFalse(obj["decision_authorized"])
            self.assertFalse(obj["order_authorized"])
            self.assertFalse(obj["thesis"]["completeness"]["all_theses_evidence_backed"])
            self.assertEqual(obj["f08_handoff"],"BLOCKED_NO_AUTHENTICATED_APPROVAL")
            self.assertEqual(obj["policy"]["status"],"DRAFT_NOT_APPROVED")
            if ready:
                self.assertEqual(len(obj["illustrative_thresholds"]),3)
                self.assertTrue(all(not x["approved"] for x in obj["illustrative_thresholds"]))
            else:
                self.assertEqual(obj["illustrative_thresholds"],[])
            self.assertEqual(obj["review_window_current"],name!="expired")
            if name=="expired":self.assertIn("REVIEW_WINDOW_EXPIRED",obj["review_gaps"])
            if name=="counter-gap":
                self.assertFalse(obj["thesis"]["completeness"]["all_theses_have_counter_research"])
            status,h,body=self.request("GET","/cases/demo/"+name,headers=c)
            self.assertEqual(status,200)
            self.assertIn("합성 기업 / 실제 투자 기준 아님".encode(),body)
            self.assertEqual(h["Cache-Control"],"no-store, private")
        self.assertEqual(self.request("POST","/api/cases",headers={**c,"Origin":ORIGIN})[0],405)

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
