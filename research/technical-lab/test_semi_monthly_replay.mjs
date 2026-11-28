import assert from "node:assert/strict";
import {monthEnds,outcome,finish,collect} from "./semi_monthly_replay.mjs";
import {periodNumber,periodLabel} from "./industry_activity.mjs";
import {IDS} from "./alfred_semiconductor.mjs";
const dates=monthEnds(),activity={phase:"EXPANSION_PROXY",period:"2022-07",metrics:[{acceleration:1},{acceleration:2}]},current={vintage:dates[0],activity};
const later={vintage:dates[3],sources:IDS.map(id=>({id,status:"PASS_SCHEMA"})),production:[{period:"2022-10",value:120},{period:"2021-10",value:100},{period:"2022-07",value:110},{period:"2021-07",value:100}]};
let n=0;async function test(name,f){await f();n++;console.log("PASS "+name)}
await test("fixed schedule including leap month",()=>{assert.equal(dates.length,51);assert.equal(dates[0],"2022-08-31");assert.equal(dates.at(-1),"2026-10-31");assert.ok(dates.includes("2024-02-29"))});
await test("same future vintage comparison and identical baseline",()=>{let x=outcome(current,later);assert.equal(x.status,"PAIRED");assert.equal(x.target,"2022-10");assert.equal(x.correct,true);assert.equal(x.baselineCorrect,true)});
await test("no future reference substitution",()=>assert.equal(outcome(current,{...later,production:later.production.slice(1)}).reason,"FUTURE_EXACT_PERIOD_MISSING"));
await test("missing later pair",()=>assert.equal(outcome(current,{...later,sources:[{status:"BLOCKED"}]}).status,"MISSING"));
await test("right censor retained",()=>assert.equal(outcome(current,undefined).status,"CENSORED"));
await test("mixed abstains",()=>assert.equal(outcome({...current,activity:{phase:"MIXED_OR_FLAT"}},later).status,"ABSTAIN"));
await test("summary excludes raw production rows and uses fixed spacing",()=>{const raw=dates.map(vintage=>({vintage,activity:{phase:"MIXED_OR_FLAT"},production:[]}));let r=finish(raw);assert.equal(r.rows.length,51);assert.equal(r.summary.counts.ABSTAIN,51);assert.equal(r.quarterSpaced.counts.ABSTAIN,17);assert.ok(r.rows.every(x=>!("production" in x)))});
await test("rate-limit stops requests and retains schedule",async()=>{let calls=0;let r=await collect(async()=>{calls++;throw Error("HTTP_429")},async()=>{});assert.equal(calls,2);assert.equal(r.rows.length,51);assert.equal(r.rows[1].activity.reason,"PROVIDER_ACCESS_OR_RATE_LIMIT_STOP")});
await test("three consecutive pair failures stop requests",async()=>{let calls=0;let r=await collect(async()=>{calls++;throw Error("HTTP_500")},async()=>{});assert.equal(calls,6);assert.equal(r.rows[3].activity.reason,"CONSECUTIVE_FAILURE_STOP")});
await test("full schedule uses both sources and retains dates",async()=>{let calls=0;const r=await collect(async(id,vintage)=>{calls++;let m=periodNumber(vintage.slice(0,7),"M");return {id,vintage,sha256:"a".repeat(64),missing:[],rows:Array.from({length:24},(_,i)=>({period:periodLabel(m-24+i,"M"),value:100+i+(id===IDS[0]?0:20)}))}},async()=>{});assert.equal(calls,102);assert.equal(r.rows.length,51);assert.ok(r.rows.every(x=>x.sources.length===2));assert.equal(Object.values(r.summary.counts).reduce((a,b)=>a+b,0),51)});
console.log(JSON.stringify({assertions:n,status:"SYNTHETIC_ONLY"}));
