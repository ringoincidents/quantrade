// Offline event study. No trading or network actions.
import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {createHash} from "node:crypto";
import {resolve,join} from "node:path";
import {parsePrices,audit} from "./engine.mjs";
import {multiTimeframe} from "./multi.mjs";
import {eventScan,eventOutcomes,summarizeEvents,eventSelfTest} from "./events.mjs";
const hash=x=>createHash("sha256").update(x).digest("hex");
const args=process.argv.slice(2);
if(args[0]==="--self-test"){console.log(JSON.stringify({assertions:eventSelfTest()}));process.exit(0)}
if(args.length!==2)throw Error("Usage: node run_events.mjs manifest.json output-directory | --self-test");
const raw=readFileSync(args[0]),m=JSON.parse(raw.toString("utf8"));
const date=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x;
if(typeof m.experimentId!=="string"||!m.experimentId.trim()||!date(m.from)||!date(m.to)||m.from>=m.to||!Array.isArray(m.assets)||!m.assets.length)throw Error("invalid event manifest");
const ids=new Set();
for(const a of m.assets){if(typeof a.asset!=="string"||!a.asset.trim()||ids.has(a.asset))throw Error("duplicate/invalid asset");ids.add(a.asset)}
const report={version:"QT-MAR-EVENT-1.0.0",status:"EXPLORATORY_NOT_VALIDATED",experimentId:m.experimentId,from:m.from,to:m.to,roundTripFactor:.995,manifestSha256:hash(raw),codeSha256:Object.fromEntries(["engine.mjs","multi.mjs","events.mjs","run_events.mjs","event_rules.json"].map(x=>[x,hash(readFileSync(new URL("./"+x,import.meta.url)))])),assets:[],summary:[],notes:["Asset-specific observed calendars; no imputation or shared portfolio simulation","Non-event comparison is an eligible risk set, not matched controls","Cross-asset and overlapping observations correlated","Right-censored outcomes null"]};
let all=[];
for(const a of m.assets){
 const e=a.prices;
 if(!e||!e.path||!e.source||!e.rights||!e.basis||!e.sha256||!["canonical","legacy-spy","plainbacktest"].includes(e.format))throw Error("missing provenance "+a.asset);
 const bytes=readFileSync(resolve(e.path)),actual=hash(bytes);
 if(actual!==e.sha256.toLowerCase())throw Error("hash mismatch "+a.asset);
 const meta={asset:a.asset,source:e.source,rights:e.rights,basis:e.basis,sha256:actual};
 try{
  const rows=parsePrices(bytes.toString("utf8"),e.format),quality=audit(rows),past=rows.filter(x=>x.d<=m.to);
  if(past.length<200||!past.some(x=>x.d>=m.from))throw Error("insufficient date coverage");
  const events=eventScan(past,multiTimeframe(past)),outcomes=eventOutcomes(past,events,{from:m.from,to:m.to}).map(x=>({...x,asset:a.asset}));
  all.push(...outcomes);
  report.assets.push({...meta,status:"USED",quality,actualFrom:past.find(x=>x.d>=m.from).d,actualTo:past.at(-1).d,summary:summarizeEvents(outcomes)});
 }catch(err){report.assets.push({...meta,status:"REJECTED",error:String(err)})}
}
if(!report.assets.some(x=>x.status==="USED"))throw Error("no usable asset");
report.summary=summarizeEvents(all);
const out=resolve(args[1]);mkdirSync(out,{recursive:true});
// Single immutable result file; event ledger includes censored observations and controls.
report.observations=all;
writeFileSync(join(out,"event_report.json"),JSON.stringify(report,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({experimentId:m.experimentId,status:report.status,used:report.assets.filter(x=>x.status==="USED").length,rejected:report.assets.filter(x=>x.status==="REJECTED").length,observations:all.length},null,2));
