"""Synthetic compatibility boundary with the existing #119 ThesisContract.

No live promotion: annotations and source provenance are not independently verified.
Use the canonical compiler to test shapes, never modify the input contract or kernel.
"""
from dataclasses import asdict,replace
from evidence_review import Claim,Evidence,packet,validate,digest,require
from quantrade.capabilities.thesis_contract import (
    ThesisContractInput,CounterClaim,compile_thesis_contract,EVIDENCE_ELIGIBLE_SOURCE_KINDS,
)

def prepare(contract,*,scope,claim_modes,evidence_kinds):
    require(scope=="SYNTHETIC_ONLY","LIVE_SCOPE_BLOCKED")
    require(isinstance(contract,ThesisContractInput),"CANONICAL_INPUT_REQUIRED")
    require(1<=len(contract.thesis_claims)<=8 and 1<=len(contract.observations)<=8,"BOUND")
    # Canonical compiler enforces point-in-time, reference integrity, falsifiability.
    compile_thesis_contract(contract)
    claims=tuple(contract.thesis_claims)
    observations=tuple(contract.observations)
    require(all(o.source_kind in EVIDENCE_ELIGIBLE_SOURCE_KINDS and o.source_ref.startswith("synthetic:") for o in observations),"SYNTHETIC_EVIDENCE_ONLY")
    require(set(claim_modes)=={c.thesis_id for c in claims},"CLAIM_ANNOTATION_COVERAGE")
    expected={(c.thesis_id,o.observation_id) for c in claims for o in observations}
    require(set(evidence_kinds)==expected,"EVIDENCE_ANNOTATION_COVERAGE")
    cs=[];es=[];sources={}
    for c in claims:
        cs.append(Claim(c.thesis_id,c.statement,claim_modes[c.thesis_id]))
        for o in observations:
            ref="e-"+digest([c.thesis_id,o.observation_id])[:40]
            require(ref not in sources,"REF_COLLISION")
            es.append(Evidence(ref,o.statement,evidence_kinds[(c.thesis_id,o.observation_id)],c.thesis_id))
            sources[ref]={"thesis_id":c.thesis_id,"observation_id":o.observation_id,"source_ref":o.source_ref,"source_kind":o.source_kind,"observed_at":o.observed_at,"statement_sha256":digest(o.statement)}
    p=packet(cs,es,case_id=contract.case_id,scope=scope)
    binding={"contract_sha256":digest(asdict(contract)),"packet":p,"source_bindings":sources,"as_of":contract.as_of,"annotation_provenance":"SYNTHETIC_CURATOR_ONLY"}
    return {"binding":binding,"binding_sha256":digest(binding)}

def preview(contract,prepared,response,*,scope,claim_modes,evidence_kinds):
    # Reconstruct binding from immutable canonical inputs. Do not trust a caller's
    # asserted review result, candidate disposition or source map.
    expected=prepare(contract,scope=scope,claim_modes=claim_modes,evidence_kinds=evidence_kinds)
    require(prepared==expected,"CANONICAL_BINDING_MISMATCH")
    b=expected["binding"];result=validate(b["packet"],response)
    counters=[];blocked=[]
    for review in result["reviews"]:
        cid=review["claim_id"]
        if review["disposition"]!="CHALLENGE":
            blocked.append({"thesis_id":cid,"status":review["disposition"]})
        for finding in review["findings"]:
            if finding["status"]!="CANDIDATE":
                blocked.append({"thesis_id":cid,"code":finding["code"],"status":finding["status"]})
                continue
            refs=tuple(sorted({b["source_bindings"][e]["observation_id"] for e in finding["evidence_ids"]}))
            counter_id="preview-"+digest([b["contract_sha256"],result["response_sha256"],cid,finding["code"]])[:40]
            # This is a synthetic preview, not an adjudicated statement.
            statement="SYNTHETIC UNVERIFIED CANDIDATE: "+finding["code"]+" | "+finding["reason"]+" | Limitation: "+finding["limitation"]
            counters.append(CounterClaim(counter_id,cid,statement,refs))
    compiled=compile_thesis_contract(replace(contract,counter_claims=contract.counter_claims+tuple(counters)))
    # Do not expose the compiled canonical artifact or its completeness flags:
    # downstream InstitutionalKernel could confuse syntactic presence with review.
    return {"schema":"qt_synthetic_counterclaim_compatibility_v1","case_id":contract.case_id,
            "binding_sha256":expected["binding_sha256"],"response_sha256":result["response_sha256"],
            "candidate_count":len(counters),"candidate_shapes":[asdict(c) for c in counters],
            "blocked_findings":blocked,"canonical_compiler_accepted":compiled.schema=="quantrade_thesis_contract_v1",
            "state":"REVIEW_REQUIRED","synthetic_only":True,"source_verified":False,
            "independent_review_completed":False,"canonical_contract_modified":False,
            "challenge_promotion_authorized":False,"committee_authorized":False,"trade_authorized":False}
