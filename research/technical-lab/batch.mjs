// Offline multi-asset replay; never calls network or trading APIs.
import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {createHash} from "node:crypto";
import {resolve,join} from "node:path";
import {parsePrices,parseMacro,audit,features,simulate,selfTest} from "./engine.mjs";
import {multiTimeframe,aggregateSleeves,mtfSelfTest} from "./multi.mjs";
import {validateBatch,batchRange,assertSameDates,batchSelfTest} from "./batch_validation.mjs";
const VERSION="QT-MAR-BATCH-1.0.0";
const hash=x=>createHash("sha256").update(x).digest("hex");
const args=process.argv.slice(2);
if(args[0]==="--self-test"){console.log(JSON.stringify({version:VERSION,engine:selfTest(),multiframe:mtfSelfTest(),batch:batchSelfTest()}));process.exit(0)}
if(args.length!==2)throw Error("Usage: node batch.mjs manifest.json output-directory | --self-test");
const rawManifest=readFileSync(args[0]),m=JSON.parse(rawManifest.toString("utf8"));validateBatch(m);
const inputs=[];
function load(key,e){
 if(!e||!e.path||!e.source||!e.rights||!e.basis||!e.sha256)throw Error("missing provenance: "+key);
 const raw=readFileSync(resolve(e.path)),actual=hash(raw);
 if(actual!==e.sha256.toLowerCase())throw Error("input hash mismatch: "+key);
 inputs.push({key,source:e.source,rights:e.rights,basis:e.basis,sha256:actual});
 return raw.toString("utf8");
}
const vm=m.vix?parseMacro(load("vix",m.vix),"CLOSE"):new Map();
const hm=m.credit?parseMacro(load("credit",m.credit),"BAMLH0A0HYM2"):new Map();
const files=["engine.mjs","multi.mjs","batch_validation.mjs","batch.mjs","rules.json"];
const report={version:VERSION,status:"EXPLORATORY_NOT_VALIDATED",experimentId:m.experimentId,from:m.from,to:m.to,fee:m.fee,manifestSha256:hash(rawManifest),codeSha256:Object.fromEntries(files.map(f=>[f,hash(readFileSync(new URL("./"+f,import.meta.url)))])),allocation:"equal initial independent sleeves; no cross-asset rebalance",calendar:"strict identical observed trading dates; not certified exchange calendar",inputs,assets:[],portfolios:[]};
let common=null;
for(const item of m.assets){
 const a=parsePrices(load("prices:"+item.asset,item.prices),item.prices.format),quality=audit(a),range=batchRange(a,m.from,m.to);
 if(common===null)common=range.dates;else assertSameDates(common,range.dates);
 // Do not expose any rows after the research end date to the snapshot builder.
 const past=a.slice(0,range.end+1),F=features(past,vm,hm);
 if(m.variants.some(v=>v.rule==="M")&&(!F[range.start].ok||!F[range.end-1].ok))throw Error("macro boundary coverage unavailable: "+item.asset);
 if(m.variants.some(v=>v.rule==="GH5")&&(!F[range.start].priorVixAvailable||!F[range.end-1].priorVixAvailable))throw Error("VIX boundary coverage unavailable: "+item.asset);
 const results=m.variants.map(({rule,mode})=>({rule,mode,...simulate(past,F,{rule,mode,from:m.from,to:m.to,fee:m.fee})}));
 const snapshot=multiTimeframe(past).at(-1);
 report.assets.push({asset:item.asset,quality,snapshot,results});
}
for(const {rule,mode} of m.variants){
 const sleeves=report.assets.map(a=>({asset:a.asset,...a.results.find(r=>r.rule===rule&&r.mode===mode)}));
 report.portfolios.push({rule,mode,...aggregateSleeves(sleeves)});
}
const out=resolve(args[1]);mkdirSync(out,{recursive:true});
writeFileSync(join(out,"batch_report.json"),JSON.stringify(report,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({experimentId:m.experimentId,status:report.status,assets:report.assets.length,sessions:common.length,portfolios:report.portfolios.map(({rule,mode,metrics})=>({rule,mode,metrics}))},null,2));
