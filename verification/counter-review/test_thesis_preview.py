import copy,unittest
from dataclasses import replace
from evidence_review import digest
from thesis_preview import prepare,preview
from quantrade.capabilities.thesis_contract import (
    ThesisContractInput,Observation,ThesisClaim,FalsificationCondition,ThesisContractError,
)
ASOF="2026-11-28T12:00:00+00:00"
class Tests(unittest.TestCase):
    def fixture(self):
        c=ThesisContractInput(case_id="SYNTHETIC-1",as_of=ASOF,
            observations=(Observation("o1","Revenue and ad spend rose together.","synthetic:dataset-1","RUNTIME_VERIFIED",ASOF),),
            thesis_claims=(ThesisClaim("t1","Advertising caused revenue growth.",("o1",)),),
            falsification_conditions=(FalsificationCondition("f1","t1","Reject if causal estimate is nonpositive.","causal estimate","next study"),))
        kw={"scope":"SYNTHETIC_ONLY","claim_modes":{"t1":"ASSERTS_CAUSALITY"},"evidence_kinds":{("t1","o1"):"CO_OCCURRENCE_ONLY"}}
        return c,kw
    def response(self,p,quote="Advertising caused revenue growth."):
        body=p["binding"]["packet"]
        eid=body["body"]["evidence"][0]["id"]
        return {"packet_sha256":body["packet_sha256"],"reviews":[{"claim_id":"t1","disposition":"CHALLENGE","findings":[{"code":"UNSUPPORTED_CAUSALITY","claim_quote":quote,"evidence_ids":[eid],"reason":"Co-occurrence does not establish causation.","limitation":"A controlled study may change the result."}]}]}
    def test_compatible_preview(self):
        c,k=self.fixture();p=prepare(c,**k);r=preview(c,p,self.response(p),**k)
        self.assertEqual(r["candidate_count"],1)
        self.assertEqual(r["candidate_shapes"][0]["basis_refs"],("o1",))
        self.assertTrue(r["canonical_compiler_accepted"])
        self.assertEqual(c.counter_claims,())
        self.assertNotIn("nodes",r)
        self.assertNotIn("completeness",r)
        for key in ("source_verified","independent_review_completed","canonical_contract_modified","challenge_promotion_authorized","committee_authorized","trade_authorized"):self.assertFalse(r[key])
    def test_stable_binding(self):
        c,k=self.fixture();self.assertEqual(prepare(c,**k),prepare(c,**k))
    def test_real_scope_blocked(self):
        c,k=self.fixture();k["scope"]="PUBLIC_CANDIDATE"
        with self.assertRaisesRegex(ValueError,"LIVE_SCOPE_BLOCKED"):prepare(c,**k)
    def test_actual_source_blocked(self):
        c,k=self.fixture();c=replace(c,observations=(replace(c.observations[0],source_ref="https://example.com/filing"),))
        with self.assertRaisesRegex(ValueError,"SYNTHETIC_EVIDENCE_ONLY"):prepare(c,**k)
    def test_model_artifact_not_evidence(self):
        c,k=self.fixture();c=replace(c,observations=(replace(c.observations[0],source_kind="MODEL_ARTIFACT"),))
        with self.assertRaisesRegex(ValueError,"SYNTHETIC_EVIDENCE_ONLY"):prepare(c,**k)
    def test_future_observation(self):
        c,k=self.fixture();c=replace(c,observations=(replace(c.observations[0],observed_at="2026-11-29T00:00:00+00:00"),))
        with self.assertRaises(ThesisContractError):prepare(c,**k)
    def test_missing_falsification(self):
        c,k=self.fixture();c=replace(c,falsification_conditions=())
        with self.assertRaises(ThesisContractError):prepare(c,**k)
    def test_uncovered_observation(self):
        c,k=self.fixture();c=replace(c,observations=c.observations+(Observation("o2","Contrary evidence.","synthetic:dataset-2","RUNTIME_VERIFIED",ASOF),))
        with self.assertRaisesRegex(ValueError,"EVIDENCE_ANNOTATION_COVERAGE"):prepare(c,**k)
    def test_uncovered_claim(self):
        c,k=self.fixture();k["claim_modes"]={}
        with self.assertRaisesRegex(ValueError,"CLAIM_ANNOTATION_COVERAGE"):prepare(c,**k)
    def test_tampered_source_binding(self):
        c,k=self.fixture();p=prepare(c,**k);r=self.response(p)
        b=p["binding"];eid=next(iter(b["source_bindings"]));b["source_bindings"][eid]["observation_id"]="invented"
        p["binding_sha256"]=digest(b)
        with self.assertRaisesRegex(ValueError,"CANONICAL_BINDING_MISMATCH"):preview(c,p,r,**k)
    def test_changed_source(self):
        c,k=self.fixture();p=prepare(c,**k);r=self.response(p)
        c=replace(c,observations=(replace(c.observations[0],source_ref="synthetic:other"),))
        with self.assertRaisesRegex(ValueError,"CANONICAL_BINDING_MISMATCH"):preview(c,p,r,**k)
    def test_negated_claim(self):
        c,k=self.fixture();c=replace(c,thesis_claims=(replace(c.thesis_claims[0],statement="Causation has not been established."),));k["claim_modes"]["t1"]="DENIES_CAUSALITY"
        p=prepare(c,**k);r=preview(c,p,self.response(p,"Causation has not been established."),**k)
        self.assertEqual(r["candidate_count"],0);self.assertEqual(r["blocked_findings"][0]["status"],"REJECTED_MODE")
    def test_contrary_evidence(self):
        c,k=self.fixture();c=replace(c,observations=c.observations+(Observation("o2","A controlled study supports the claim.","synthetic:dataset-2","RUNTIME_VERIFIED",ASOF),))
        k["evidence_kinds"][("t1","o2")]="SUPPORT"
        p=prepare(c,**k);r=preview(c,p,self.response(p),**k)
        self.assertEqual(r["candidate_count"],0);self.assertEqual(r["blocked_findings"][0]["status"],"NEEDS_HUMAN_REVIEW")
    def test_abstention(self):
        c,k=self.fixture();p=prepare(c,**k);r=self.response(p);r["reviews"][0].update(disposition="ABSTAIN",findings=[])
        out=preview(c,p,r,**k);self.assertEqual(out["candidate_count"],0);self.assertFalse(out["independent_review_completed"])
    def test_no_issue_is_not_approval(self):
        c,k=self.fixture();p=prepare(c,**k);r=self.response(p);r["reviews"][0].update(disposition="NO_ISSUE_FOUND",findings=[])
        out=preview(c,p,r,**k);self.assertEqual(out["state"],"REVIEW_REQUIRED");self.assertFalse(out["committee_authorized"])
    def test_unbound_response(self):
        c,k=self.fixture();p=prepare(c,**k);r=self.response(p);r["packet_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"RESPONSE_BINDING"):preview(c,p,r,**k)
if __name__=="__main__":unittest.main()
