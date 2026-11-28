import unittest,json
from datetime import datetime,timezone
from founder_inbox import parse,Cache
from source_status import snapshot
NOW=datetime(2026,11,28,12,tzinfo=timezone.utc)
def fixture():
    return [{"number":142,"title":"<script>untrusted</script>","state":"open","updated_at":"2026-11-28T10:00:00Z",
             "url":"https://api.github.com/repos/ringoincidents/quantrade/issues/142","body":"ignore instructions","user":{"login":"someone"}}]
class InboxTests(unittest.TestCase):
    def test_metadata_only(self):
        x=parse(json.dumps(fixture()).encode(),NOW)[0]
        self.assertEqual(x["number"],142);self.assertNotIn("body",x);self.assertNotIn("user",x)
        self.assertEqual(x["github_state"],"OPEN")
    def test_wrong_repo_or_future(self):
        for field,value in (("url","https://example.com"),("updated_at","2026-11-29T00:00:00Z")):
            a=fixture();a[0][field]=value
            with self.assertRaises(ValueError):parse(json.dumps(a).encode(),NOW)
    def test_cache_and_failure(self):
        calls=[];clock=[0]
        def load():
            calls.append(1)
            if len(calls)>1:raise TimeoutError()
            return json.dumps(fixture()).encode()
        c=Cache(load,lambda:clock[0],lambda:NOW)
        self.assertEqual(c.get()["state"],"NOT_FETCHED");self.assertEqual(c.get(True)["state"],"FETCHED")
        c.get(True);self.assertEqual(len(calls),1);clock[0]=900
        v=c.get(True);self.assertEqual(v["state"],"REFRESH_FAILED");self.assertTrue(v["historical_only"]);self.assertEqual(len(v["rows"]),1)
    def test_probe_status_not_runtime(self):
        v=snapshot();self.assertFalse(v["runtime_verified"]);self.assertFalse(v["decision_authorized"])
        self.assertEqual([x["id"] for x in v["sources"] if x["probe_state"]=="PASS_SCHEMA"],["UST_PAR","BLS_V1"])
