// Frozen research only. No production integration or execution authority.
import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {resolve} from "node:path";
import {parsePrices,audit} from "./engine.mjs";
import {multiTimeframe} from "./multi.mjs";
import {eventScan,eventOutcomes} from "./events.mjs";
const hash=x=>createHash("sha256").update(x).digest("hex");
const a=process.argv.slice(2);if(a.length!==4)throw Error("Usage: node run_universe.mjs inventory.json audit.json source-root output.json");
const ib=readFileSync(a[0]),ab=readFileSync(a[1]),inv=JSON.parse(ib),quality=JSON.parse(ab);
if(quality.inventorySha256!==hash(ib)||quality.files.length!==inv.files.length)throw Error("inventory/audit mismatch");
const qm=new Map(quality.files.map(x=>[x.path,x]));
if(qm.size!==inv.files.length)throw Error("duplicate audit path");
const spyPath="data/processed/daily/SPY.csv",spySha="6b07e1636b1ecc276f17d6d474bb9ec864f7efe829d955c1f83d9f84088f4313";
const spyBytes=readFileSync(resolve(a[2],spyPath));if(hash(spyBytes)!==spySha)throw Error("SPY hash mismatch");
const spy=parsePrices(spyBytes.toString(),"plainbacktest");audit(spy);
const market=new Map(spy.map((x,i)=>[x.d,{...x,regime:i<199?null:x.p>=spy.slice(i-199,i+1).reduce((s,z)=>s+z.p,0)/200?"ABOVE_SMA200":"BELOW_SMA200"}]));
const frozen=new Set(["Y_RECLAIM3","M_COMP_BREAK","M_SUPPORT100"]),from="2001-01-01",to="2026-08-04";
// Already viewed assets cannot become independent validation securities.
const seen=new Set("SPY QQQ AAPL MSFT XOM JPM KO GE AEE AON BBY CAG CLF CRWD DIS EMN FDX GCO HD INTC KKR LUV MNST NEM OMC PNW RL SNA TECH TXN VNT WTW AM-201308 BNI-201002 CMB-199603 DOW-201708 GAS-201606 HSH-201408 LSI-201405 NCR-199109 PMI-199911 SFS-200008 TIE-201301 WBA-202508".split(" "));
const role=id=>seen.has(id)?"PREVIOUSLY_VIEWED":parseInt(hash("QT-MAR-universe-v1:"+id).slice(0,8),16)%5===0?"SECURITY_HOLDOUT":"EXPANSION";
const rows=[],assets=[];
for(const f of inv.files){
 const id=f.path.split("/").at(-1).replace(/\.csv$/,""),q=qm.get(f.path),group=role(id);
 if(!q)throw Error("missing audit row");
 if(q.status!=="PRICE_SHAPE_PASS_NOT_G0"){assets.push({asset:id,group,status:q.status});continue}
 try{
  const bytes=readFileSync(resolve(a[2],f.path));if(hash(bytes)!==f.sha256)throw Error("snapshot mismatch");
  const raw=parsePrices(bytes.toString(),"plainbacktest");audit(raw);
  const past=raw.filter(x=>x.d<=to);if(past.length<200||!past.some(x=>x.d>=from)){assets.push({asset:id,group,status:"NO_DECISION_COVERAGE"});continue}
  const hits=eventScan(past,multiTimeframe(past)).filter(x=>frozen.has(x.rule));
  for(const e of eventOutcomes(past,hits,{from,to})){
   const s=market.get(e.date),en=e.result&&market.get(e.result.entryDate),ex=e.result&&market.get(e.result.exitDate);
   const marketRet=en&&ex?ex.p/en.o*.995-1:null;
   rows.push({...e,asset:id,group,marketRegime:s?.regime??null,marketRet,marketExcess:marketRet===null?null:e.result.ret-marketRet});
  }
  assets.push({asset:id,group,status:"USED_EXPLORATORY",events:hits.filter(x=>x.date>=from&&x.date<=to).length});
 }catch(e){assets.push({asset:id,group,status:"ERROR",error:String(e)})}
}
const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
const stats=z=>{let v=z.filter(x=>x.result),m=v.filter(x=>x.marketExcess!==null);return {eligible:z.length,complete:v.length,censored:z.length-v.length,return:mean(v.map(x=>x.result.ret)),adverse10:mean(v.map(x=>+x.result.hit10)),marketMatched:m.length,marketExcess:mean(m.map(x=>x.marketExcess))}};
const summary=[];for(const group of ["PREVIOUSLY_VIEWED","EXPANSION","SECURITY_HOLDOUT"])for(const rule of frozen)for(const h of [5,20,60,120])for(const regime of ["ALL","ABOVE_SMA200","BELOW_SMA200"])for(const hit of [true,false]){
 const z=rows.filter(x=>x.group===group&&x.rule===rule&&x.h===h&&x.hit===hit&&(regime==="ALL"||x.marketRegime===regime));summary.push({group,rule,h,regime,hit,...stats(z)});
}
const report={status:"EXPLORATORY_NOT_VALIDATED",from,to,inventorySha256:hash(ib),auditSha256:hash(ab),spySha256:spySha,codeSha256:Object.fromEntries(["engine.mjs","multi.mjs","events.mjs","event_rules.json","run_universe.mjs"].map(x=>[x,hash(readFileSync(new URL("./"+x,import.meta.url)))])),assets,summary,observations:rows,limitations:["Quarantined >35% jumps and invalid files; no corporate-action or terminal-payout reconstruction. Not PIT membership certified.","Security holdout assigned by fixed hash before expanded outcomes; same calendar history, not independent temporal holdout. Previously viewed names excluded from holdout; other prior research exposure not audited.","SPY adjusted-price return approximates benchmark, exact entry/exit date match only. Sector benchmark unavailable.","Gross MAE and hit10, .995 uniform cost factor; no actual liquidity or execution certification. No trade or production use."]};
writeFileSync(a[3],JSON.stringify(report)+"\n",{flag:"wx"});
console.log(JSON.stringify({assets:assets.length,used:assets.filter(x=>x.status==="USED_EXPLORATORY").length,rows:rows.length,primary:summary.filter(x=>x.h===60&&x.regime==="ALL")},null,2));
