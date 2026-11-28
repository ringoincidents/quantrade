import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {createHash} from "node:crypto";
import {resolve,join} from "node:path";
import {parsePrices,parseMacro,audit,features,simulate,selfTest} from "./engine.mjs";
const VERSION="QT-MAR-REPLAY-1.0.0";
const hash=s=>createHash("sha256").update(s).digest("hex");
const args=process.argv.slice(2);
if(args[0]==="--self-test"){console.log(JSON.stringify({version:VERSION,assertions:selfTest()}));process.exit(0)}
if(args.length!==2)throw Error("Usage: node run.mjs manifest.json output-directory | --self-test");
const manifestText=readFileSync(args[0],"utf8"),m=JSON.parse(manifestText);
if(!m.experimentId||!m.asset||!m.from||!m.to||!Array.isArray(m.variants)||!m.variants.length||!Number.isFinite(m.fee)||!["canonical","legacy-spy","plainbacktest"].includes(m.prices?.format))throw Error("incomplete manifest");
const inputs={};
function load(key,entry){
 if(!entry||!entry.path||!entry.source||!entry.rights||!entry.basis||!entry.sha256)throw Error("missing provenance for "+key);
 const raw=readFileSync(resolve(entry.path)),actual=hash(raw);
 if(actual!==entry.sha256.toLowerCase())throw Error("input hash mismatch: "+key);
 inputs[key]={source:entry.source,rights:entry.rights,basis:entry.basis,sha256:actual};
 return raw.toString("utf8");
}
const a=parsePrices(load("prices",m.prices),m.prices.format),quality=audit(a);
const vm=m.vix?parseMacro(load("vix",m.vix),"CLOSE"):new Map();
const hm=m.credit?parseMacro(load("credit",m.credit),"BAMLH0A0HYM2"):new Map();
const F=features(a,vm,hm);
const report={version:VERSION,status:"EXPLORATORY_NOT_VALIDATED",experimentId:m.experimentId,asset:m.asset,from:m.from,to:m.to,fee:m.fee,manifestSha256:hash(manifestText),engineSha256:hash(readFileSync(new URL("./engine.mjs",import.meta.url))),rulesSha256:hash(readFileSync(new URL("./rules.json",import.meta.url))),runnerSha256:hash(readFileSync(new URL("./run.mjs",import.meta.url))),inputs,quality,results:[]};
const seen=new Set();
for(const variant of m.variants){
 const {rule,mode}=variant,id=rule+"-"+mode;
 if(seen.has(id))throw Error("duplicate variant");seen.add(id);
 if(rule==="M"&&(!m.credit||!m.vix))throw Error("M requires credit and VIX");
 if(rule==="GH5"&&!m.vix)throw Error("GH5 requires VIX");
 report.results.push({rule,mode,...simulate(a,F,{rule,mode,from:m.from,to:m.to,fee:m.fee})});
}
const out=resolve(args[1]);mkdirSync(out,{recursive:true});
writeFileSync(join(out,"report.json"),JSON.stringify(report,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({experimentId:m.experimentId,status:report.status,results:report.results.map(({rule,mode,metrics})=>({rule,mode,metrics}))},null,2));
