import assert from "node:assert/strict";
import {CONTRACT,evaluate,periodLabel,periodNumber} from "./industry_activity.mjs";
const E={status:"VERIFIED",rights:"RESEARCH_ALLOWED",evidenceSha256:"a".repeat(64)};
const asOf="2026-11-28T12:00:00Z",industry=CONTRACT.industries[0],quarter=CONTRACT.industries[4];
const known="2026-11-15T12:00:00Z";
function series(ind,values,periods=["2026-10","2025-10","2026-07","2025-07"]){
 return ind.metrics.map((m,i)=>({...E,id:m.id,source:m.source,frequency:ind.frequency,unit:m.unit,capturedAt:asOf,observations:periods.map((period,j)=>({...E,source:m.source,period,value:values[i][j],knownAt:known}))}));
}
const expansion=[[120,100,110,100],[85,75,80,75]],slow=[[110,100,120,100],[80,75,85,75]],recovery=[[95,100,80,100],[73,75,65,75]],contraction=[[80,100,95,100],[65,75,73,75]];
const run=(s,at=asOf)=>evaluate({contractVersion:CONTRACT.version,asOf:at,series:s});
const first=(s,at)=>run(s,at).industries[0];
let count=0;function test(name,f){f();count++;console.log("PASS "+name)}
test("expansion",()=>assert.equal(first(series(industry,expansion)).phase,"EXPANSION_PROXY"));
test("slowdown",()=>assert.equal(first(series(industry,slow)).phase,"SLOWDOWN_PROXY"));
test("recovery",()=>assert.equal(first(series(industry,recovery)).phase,"RECOVERY_PROXY"));
test("contraction",()=>assert.equal(first(series(industry,contraction)).phase,"CONTRACTION_PROXY"));
test("conflicting indicators abstain",()=>assert.equal(first(series(industry,[expansion[0],contraction[1]])).phase,"MIXED_OR_FLAT"));
test("flat indicator abstains",()=>assert.equal(first(series(industry,[expansion[0],[75,75,75,75]])).phase,"MIXED_OR_FLAT"));
test("all five missing industries blocked",()=>assert.ok(run([]).industries.every(x=>x.status==="BLOCKED")));
test("no approximate period substitution",()=>{let s=series(industry,expansion);s[0].observations=s[0].observations.filter(o=>o.period!=="2025-10");assert.equal(first(s).reason,"INSUFFICIENT_EXACT_HISTORY")});
test("stale series blocked",()=>assert.equal(first(series(industry,expansion,["2026-07","2025-07","2026-04","2025-04"])).reason,"STALE_OR_MISALIGNED_SERIES"));
test("latest common period and lag",()=>{let s=series(industry,expansion);s[0].observations.push({...s[0].observations[0],period:"2026-11",knownAt:"2026-12-01T00:00:00Z"});s[0].capturedAt="2026-12-02T00:00:00Z";assert.equal(first(s).period,"2026-10")});
test("future vintage excluded",()=>{let s=series(industry,expansion);s[0].observations.push({...s[0].observations[0],knownAt:"2026-12-03T00:00:00Z",value:70});s[0].capturedAt="2026-12-04T00:00:00Z";assert.equal(first(s).phase,"EXPANSION_PROXY");assert.equal(first(s,"2026-12-04T00:00:00Z").phase,"MIXED_OR_FLAT")});
test("last known revision selected independent of row order",()=>{let s=series(industry,expansion);s[0].observations.unshift({...s[0].observations[0],knownAt:"2026-11-20T00:00:00Z",value:70});assert.equal(first(s).phase,"MIXED_OR_FLAT")});
test("duplicate vintage rejected",()=>{let s=series(industry,expansion);s[0].observations.push(s[0].observations[0]);assert.throws(()=>first(s))});
test("publication before reference period ends rejected",()=>{let s=series(industry,expansion);s[0].observations[0].knownAt="2026-10-15T00:00:00Z";assert.throws(()=>first(s))});
test("publication later than capture rejected",()=>{let s=series(industry,expansion);s[0].capturedAt="2026-11-01T00:00:00Z";assert.throws(()=>first(s))});
test("unverified evidence rejected",()=>{let s=series(industry,expansion);s[0].observations[0].status="UNVERIFIED";assert.throws(()=>first(s))});
test("unknown rights rejected",()=>{let s=series(industry,expansion);s[0].rights="UNKNOWN";assert.throws(()=>first(s))});
test("wrong measurement basis rejected",()=>{let s=series(industry,expansion);s[0].unit="NOMINAL_USD";assert.throws(()=>first(s))});
test("positive denominator required",()=>{let s=series(industry,expansion);s[0].observations[1].value=0;assert.throws(()=>first(s))});
test("percentage points not percent change",()=>{let x=first(series(industry,expansion));assert.equal(x.metrics[1].growth,10);assert.equal(x.metrics[1].unit,"pp")});
test("quarterly banking cross-year alignment and negative ROA accepted",()=>{let s=series(quarter,[[120,100,110,100],[1,-1,0,-1]],["2026-Q3","2025-Q3","2026-Q2","2025-Q2"]);let x=run(s).industries[4];assert.equal(x.phase,"EXPANSION_PROXY");assert.equal(x.metrics[1].growth,2)});
test("period round trip",()=>{for(const [p,f] of [["2026-Q1","Q"],["2026-01","M"],["2026-12","M"]])assert.equal(periodLabel(periodNumber(p,f),f),p);assert.throws(()=>periodNumber("2026-13","M"))});
test("different source rejected",()=>{let s=series(industry,expansion);s[0].source="OTHER";assert.throws(()=>first(s))});
test("invalid as-of timestamp rejected",()=>assert.throws(()=>run([],"2026-02-30T12:00:00Z")));
console.log(JSON.stringify({assertions:count,status:"SYNTHETIC_ONLY"}));
