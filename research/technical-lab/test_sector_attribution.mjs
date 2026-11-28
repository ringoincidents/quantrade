import assert from "node:assert/strict";
import {makeContext,attributeEvent,sectorContext} from "./sector_attribution.mjs";
const E={status:"VERIFIED",source:"SYNTHETIC_FIXTURE",evidenceSha256:"a".repeat(64),rights:"RESEARCH_ALLOWED"};
const dates=Array.from({length:130},(_,i)=>new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10)); // synthetic calendar, NOT real exchange dates
const t=d=>d+"T21:00:00Z",sessions=dates.map(date=>({date,closeAt:t(date)})),asOf=t(dates.at(-1));
const series=(id,kind,rate)=>({...E,id,kind,currency:"USD",basis:"TOTAL_RETURN_ADJUSTED_PROXY",capturedAt:asOf,bars:dates.map((date,i)=>({date,open:100+i*rate,close:100+i*rate,knownAt:t(date)}))});
const mapping={...E,asset:"A",securityId:"PERM_A",sectorId:"TEST_SECTOR",benchmarkId:"SECTOR",from:dates[0],to:null,knownAt:t(dates[0])};
const fixture={calendarEvidence:E,sessions,mappings:[mapping],series:[series("MARKET","MARKET",1),series("SECTOR","SECTOR",2)]};
const e={asset:"A",rule:"Y_RECLAIM3",hit:true,h:5,date:dates[20],result:{entryDate:dates[21],exitDate:dates[25],ret:.10},marketRet:125/121*.995-1};
const call=(f=fixture,event=e,cutoff=asOf)=>attributeEvent(makeContext(f),event,{marketId:"MARKET",asOf:cutoff});
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-12);
let n=0;
const test=(name,f)=>{f();n++;console.log("PASS "+name)};
test("same-date sector and market decomposition",()=>{let x=call();assert.equal(x.status,"EXPLORATORY_MATCH");near(x.sectorReturn,150/142*.995-1);near(x.stockVsMarket,x.stockVsSector+x.sectorVsMarket)});
test("PIT future-known sector assignment cannot leak",()=>assert.equal(call({...fixture,mappings:[{...mapping,knownAt:t(dates[21])}]}).reason,"PIT_MAPPING_MISSING"));
test("half-open classification intervals",()=>assert.equal(call({...fixture,mappings:[{...mapping,to:dates[20]}]}).reason,"PIT_MAPPING_MISSING"));
test("conflicting classifications fail closed",()=>assert.equal(call({...fixture,mappings:[mapping,{...mapping,sectorId:"OTHER"}]}).reason,"PIT_MAPPING_CONFLICT"));
test("unverified evidence rejected",()=>assert.throws(()=>makeContext({...fixture,mappings:[{...mapping,status:"UNVERIFIED"}]})));
test("unknown rights rejected",()=>assert.throws(()=>makeContext({...fixture,series:[{...fixture.series[0],rights:"UNKNOWN"},fixture.series[1]]})));
test("mixed currency rejected",()=>assert.throws(()=>makeContext({...fixture,series:[{...fixture.series[0],currency:"KRW"},fixture.series[1]]})));
test("incomparable price basis rejected",()=>assert.throws(()=>makeContext({...fixture,series:[{...fixture.series[0],basis:"RAW"},fixture.series[1]]})));
test("missing intermediate sector session blocks",()=>assert.equal(call({...fixture,series:[fixture.series[0],{...fixture.series[1],bars:fixture.series[1].bars.filter(b=>b.date!==dates[23])}]}).reason,"BENCHMARK_WINDOW_INCOMPLETE_OR_UNAVAILABLE"));
test("delayed bar availability blocks",()=>{let s=fixture.series[1];let changed={...s,bars:s.bars.map(b=>b.date===dates[25]?{...b,knownAt:t(dates[26])}:b)};assert.equal(call({...fixture,series:[fixture.series[0],changed]},e,t(dates[25])).reason,"BENCHMARK_WINDOW_INCOMPLETE_OR_UNAVAILABLE")});
test("wrong market return blocks",()=>assert.equal(call(fixture,{...e,marketRet:0}).reason,"ORIGINAL_MARKET_RETURN_MISMATCH"));
test("missing benchmark mapping blocks",()=>assert.equal(call({...fixture,mappings:[{...mapping,benchmarkId:"MISSING"}]}).reason,"BENCHMARK_MISSING_OR_WRONG_KIND"));
test("censored outcome remains unknown",()=>assert.equal(call(fixture,{...e,result:null}).reason,"CENSORED_UNRESOLVED"));
test("wrong horizon blocks",()=>assert.equal(call(fixture,{...e,result:{...e.result,exitDate:dates[26]}}).reason,"REFERENCE_HORIZON_MISMATCH"));
test("future outcome blocked",()=>assert.equal(call(fixture,e,t(dates[24])).reason,"OUTCOME_NOT_YET_KNOWN"));
test("duplicate benchmark rejected",()=>assert.throws(()=>makeContext({...fixture,series:[...fixture.series,fixture.series[0]]})));
test("price known before session close rejected",()=>{let s=fixture.series[0];assert.throws(()=>makeContext({...fixture,series:[{...s,bars:[{...s.bars[0],knownAt:dates[0]+"T12:00:00Z"},...s.bars.slice(1)]},fixture.series[1]]}))});
test("descriptive context exact horizons",()=>{let x=sectorContext(makeContext(fixture),{sectorId:"SECTOR",marketId:"MARKET",date:dates[129],asOf});assert.equal(x.status,"DESCRIPTIVE_ONLY");assert.deepEqual(x.windows.map(w=>w.h),[20,60,120]);near(x.windows[0].relativeReturn,358/318-229/209)});
test("insufficient context is partial",()=>{let x=sectorContext(makeContext(fixture),{sectorId:"SECTOR",marketId:"MARKET",date:dates[20],asOf:t(dates[20])});assert.deepEqual(x.windows.map(w=>w.status),["DESCRIPTIVE","BLOCKED","BLOCKED"])});
test("context does not use future price bars",()=>{let a=sectorContext(makeContext(fixture),{sectorId:"SECTOR",marketId:"MARKET",date:dates[60],asOf:t(dates[60])}),s=fixture.series[1],b=sectorContext(makeContext({...fixture,series:[fixture.series[0],{...s,bars:s.bars.slice(0,61)}]}),{sectorId:"SECTOR",marketId:"MARKET",date:dates[60],asOf:t(dates[60])});assert.deepEqual(a,b)});

import {mkdtempSync,writeFileSync,readFileSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
test("CLI lineage, immutable result, blocked rows",()=>{
 const d=mkdtempSync(join(tmpdir(),"qt-sector-"));
 try{
 const sha=x=>createHash("sha256").update(x).digest("hex"),write=(name,v)=>{let p=join(d,name),b=JSON.stringify(v);writeFileSync(p,b);return [p,sha(b)]};
 const [ap,ah]=write("audit.json",{inventorySha256:"fixture",files:[{}]});
 const [up,uh]=write("universe.json",{inventorySha256:"fixture",auditSha256:ah,assets:[{asset:"A",status:"USED_EXPLORATORY"}],observations:[{...e,group:"TEST"},{...e,group:"TEST",result:null}]});
 const [ip,ih]=write("sector.json",{...fixture,universeSha256:uh,marketId:"MARKET",asOf,contextRequests:[]});
 const out=join(d,"result.json"),cli=fileURLToPath(new URL("./run_sector_attribution.mjs",import.meta.url));
 const run=hash=>spawnSync(process.execPath,[cli,ap,up,ip,hash,out],{encoding:"utf8"});
 assert.notEqual(run("0".repeat(64)).status,0);
 const good=run(ih);assert.equal(good.status,0,good.stderr);
 const p=JSON.parse(readFileSync(out,"utf8"));assert.equal(p.summary[0].matched,1);assert.equal(p.summary[0].coverage,.5);assert.equal(p.summary[0].blocked.CENSORED_UNRESOLVED,1);
 assert.notEqual(run(ih).status,0);
 }finally{rmSync(d,{recursive:true,force:true})}
});
console.log(JSON.stringify({assertions:n,status:"SYNTHETIC_ONLY"}));
