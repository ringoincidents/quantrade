import unittest,copy
from evidence_review import Claim,Evidence,packet,validate,digest

class EvidenceReviewTests(unittest.TestCase):
    def make(self,mode="ASSERTS_CAUSALITY",kind="CO_OCCURRENCE_ONLY",text="Advertising caused revenue growth.",code="UNSUPPORTED_CAUSALITY",more=()):
        p=packet([Claim("c1",text,mode)],[Evidence("e1","Sales and advertising moved together.",kind,"c1"),*more],case_id="SYNTHETIC-01",scope="SYNTHETIC_ONLY")
        r={"packet_sha256":p["packet_sha256"],"reviews":[{"claim_id":"c1","disposition":"CHALLENGE","findings":[{"code":code,"claim_quote":text,"evidence_ids":["e1"],"reason":"Scope of evidence does not support conclusion.","limitation":"Further independent evidence may change this."}]}]}
        return p,r
    def status(self,p,r):return validate(p,r)["reviews"][0]["findings"][0]["status"]
    def test_causal_assertion(self):
        p,r=self.make();self.assertEqual(self.status(p,r),"CANDIDATE")
    def test_negation_regression(self):
        p,r=self.make(mode="DENIES_CAUSALITY",text="Both rose; causation has not been established.")
        self.assertEqual(self.status(p,r),"REJECTED_MODE")
    def test_hypothesis_not_assertion(self):
        p,r=self.make(mode="HYPOTHESIZES_CAUSALITY",text="Advertising may have contributed; more study is needed.")
        self.assertEqual(self.status(p,r),"REJECTED_MODE")
    def test_positive_descriptive(self):
        p,r=self.make(mode="DESCRIPTIVE",text="Sales and advertising rose.")
        self.assertEqual(self.status(p,r),"REJECTED_MODE")
    def test_buy(self):
        p,r=self.make(mode="ASSERTS_BUY",kind="NO_VALUATION_OR_RISK",code="UNSUPPORTED_BUY_CLAIM",text="Buy irrespective of price.")
        self.assertEqual(self.status(p,r),"CANDIDATE")
    def test_extrapolation(self):
        p,r=self.make(mode="ASSERTS_GUARANTEE",kind="SINGLE_PERIOD_ONLY",code="UNSUPPORTED_EXTRAPOLATION",text="Future earnings are guaranteed.")
        self.assertEqual(self.status(p,r),"CANDIDATE")
    def test_contradiction(self):
        p,r=self.make(mode="DESCRIPTIVE",kind="EXPLICIT_CONTRADICTION",code="CONTRADICTS_EVIDENCE")
        self.assertEqual(self.status(p,r),"CANDIDATE")
    def test_unknown(self):
        p,r=self.make(mode="UNKNOWN");self.assertEqual(self.status(p,r),"NEEDS_HUMAN_REVIEW")
    def test_counterevidence_cannot_be_omitted(self):
        p,r=self.make(more=(Evidence("e2","A separate study supports the claim.","SUPPORT","c1"),))
        self.assertEqual(self.status(p,r),"NEEDS_HUMAN_REVIEW")
    def test_uncited_support_for_challenge(self):
        p,r=self.make(kind="CO_OCCURRENCE_ONLY",more=(Evidence("e2","Unclear.","SINGLE_PERIOD_ONLY","c1"),))
        r["reviews"][0]["findings"][0]["evidence_ids"]=["e2"]
        self.assertEqual(self.status(p,r),"NEEDS_HUMAN_REVIEW")
    def test_wrong_quote(self):
        p,r=self.make();r["reviews"][0]["findings"][0]["claim_quote"]="Made up quote"
        with self.assertRaisesRegex(ValueError,"CLAIM_QUOTE"):validate(p,r)
    def test_made_up_evidence(self):
        p,r=self.make();r["reviews"][0]["findings"][0]["evidence_ids"]=["fake"]
        with self.assertRaisesRegex(ValueError,"EVIDENCE_BINDING"):validate(p,r)
    def test_cross_claim_evidence(self):
        p,r=self.make();b=p["body"];b["claims"].append({"id":"c2","text":"Other claim","mode":"DESCRIPTIVE"});b["evidence"].append({"id":"e2","text":"Other evidence","kind":"CO_OCCURRENCE_ONLY","claim_id":"c2"})
        p["packet_sha256"]=digest(b);r["packet_sha256"]=p["packet_sha256"];r["reviews"].append({"claim_id":"c2","disposition":"ABSTAIN","findings":[]});r["reviews"][0]["findings"][0]["evidence_ids"]=["e2"]
        with self.assertRaisesRegex(ValueError,"EVIDENCE_BINDING"):validate(p,r)
    def test_tampered_packet(self):
        p,r=self.make();p["body"]["claims"][0]["text"]="changed"
        with self.assertRaisesRegex(ValueError,"PACKET_DIGEST"):validate(p,r)
    def test_wrong_response_binding(self):
        p,r=self.make();r["packet_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"RESPONSE_BINDING"):validate(p,r)
    def test_coverage(self):
        p,r=self.make();r["reviews"]=[]
        with self.assertRaisesRegex(ValueError,"REVIEW_COVERAGE"):validate(p,r)
    def test_abstain(self):
        p,r=self.make();r["reviews"][0].update(disposition="ABSTAIN",findings=[])
        result=validate(p,r);self.assertEqual(result["reviews"][0]["disposition"],"ABSTAIN");self.assertEqual(result["state"],"REVIEW_REQUIRED")
    def test_no_issue_is_not_approval(self):
        p,r=self.make();r["reviews"][0].update(disposition="NO_ISSUE_FOUND",findings=[])
        result=validate(p,r)
        for k in ("independent_review_completed","challenge_promotion_authorized","committee_authorized","trade_authorized"):self.assertFalse(result[k])
    def test_authority_injection(self):
        p,r=self.make();r["approved"]=True
        with self.assertRaisesRegex(ValueError,"RESPONSE_SCHEMA"):validate(p,r)
    def test_numeric_override(self):
        p,r=self.make();r["reviews"][0]["findings"][0]["code"]="BALANCE_MISMATCH"
        with self.assertRaisesRegex(ValueError,"FINDING_CODE"):validate(p,r)
    def test_no_real_private_scope(self):
        with self.assertRaisesRegex(ValueError,"SCOPE"):packet([Claim("c","test","UNKNOWN")],[Evidence("e","test","UNKNOWN","c")],case_id="x",scope="PRIVATE")
if __name__=="__main__":unittest.main()
