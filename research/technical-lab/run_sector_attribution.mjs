// Offline secondary attribution; input is an externally reviewed private research bundle.
import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {makeContext,attributeEvent,sectorContext} from "./sector_attribution.mjs";
const sha=b=>createHash("sha256").update(b).digest("hex");
const args=process.argv.slice(2);
if(args.length!==5)throw Error("Usage: node run_sector_attribution.mjs audit.json universe.json sector-input.json expected-input-sha256 output.json");
const [ab,ub,ib]=args.slice(0,3).map(p=>readFileSync(p));
if(!/^[a-f0-9]{64}$/.test(args[3])||sha(ib)!==args[3])throw Error("sector input hash mismatch");
const audit=JSON.parse(ab),universe=JSON.parse(ub),input=JSON.parse(ib);
if(universe.auditSha256!==sha(ab)||universe.inventorySha256!==audit.inventorySha256||!Array.isArray(universe.assets)||!Array.isArray(audit.files)||universe.assets.length!==audit.files.length||!Array.isArray(universe.observations))throw Error("universe provenance mismatch");
if(input.universeSha256!==sha(ub)||typeof input.marketId!=="string"||typeof input.asOf!=="string"||!Array.isArray(input.contextRequests))throw Error("input is not bound to this universe");
const ctx=makeContext(input),groups=new Map();
const allowed=new Set(universe.assets.filter(a=>a.status==="USED_EXPLORATORY").map(a=>a.asset));
const rows=universe.observations.map(e=>{
 if(!allowed.has(e.asset))throw Error("event asset not in used universe");
 const a=attributeEvent(ctx,e,{marketId:input.marketId,asOf:input.asOf});
 const key=JSON.stringify([e.group,e.rule,e.h,e.hit]);
 if(!groups.has(key))groups.set(key,{group:e.group,rule:e.rule,h:e.h,hit:e.hit,eligible:0,matched:0,blocked:{},stockVsSectorSum:0,sectorVsMarketSum:0,stockVsMarketSum:0});
 const g=groups.get(key);g.eligible++;
 if(a.status==="EXPLORATORY_MATCH"){g.matched++;g.stockVsSectorSum+=a.stockVsSector;g.sectorVsMarketSum+=a.sectorVsMarket;g.stockVsMarketSum+=a.stockVsMarket}
 else g.blocked[a.reason]=(g.blocked[a.reason]??0)+1;
 return {asset:e.asset,group:e.group,rule:e.rule,h:e.h,hit:e.hit,date:e.date,...a}
});
const summary=[...groups.values()].map(({stockVsSectorSum,sectorVsMarketSum,stockVsMarketSum,...g})=>({...g,coverage:g.matched/g.eligible,meanStockVsSector:g.matched?stockVsSectorSum/g.matched:null,meanSectorVsMarket:g.matched?sectorVsMarketSum/g.matched:null,meanStockVsMarket:g.matched?stockVsMarketSum/g.matched:null}));
const contexts=input.contextRequests.map(x=>sectorContext(ctx,{...x,marketId:input.marketId,asOf:x.asOf??input.asOf}));
const report={status:"EXPLORATORY_NOT_VALIDATED",inputSha256:sha(ib),auditSha256:sha(ab),universeSha256:sha(ub),codeSha256:Object.fromEntries(["sector_attribution.mjs","run_sector_attribution.mjs"].map(f=>[f,sha(readFileSync(new URL("./"+f,import.meta.url)))])),asOf:input.asOf,summary,contexts,rows,limitations:["Evidence and rights fields are external attestations, not independently authenticated by this program.","Stock outcomes inherited from frozen exploratory run; no corporate-action, intrawindow stock-bar or true execution certification.","Sector index/ETF proxy may include the subject stock. Not independent peers or causal attribution.","Historical membership is selected using only effective and known dates at signal close. Classification/identity source must be independently reviewed.","Context is price-relative description, not macroeconomic or business-cycle classification; later revisions may be used if request asOf allows them.","No investment approval, rankings, signals or orders."]};
writeFileSync(args[4],JSON.stringify(report,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({status:report.status,observations:rows.length,matched:rows.filter(x=>x.status==="EXPLORATORY_MATCH").length,blocked:rows.filter(x=>x.status==="BLOCKED").length}));
