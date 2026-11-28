import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
// Fixed secondary diagnostics; already observed samples, not a holdout.
function diagnostics(batches){
 const rows=batches.flat().flatMap(a=>a.events),rules=["Y_RECLAIM3","M_COMP_BREAK","M_SUPPORT100"];
 const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
 const quant=(a,p)=>a[Math.floor(p*(a.length-1))];
 const groups=(a,key)=>{let m=new Map;for(const x of a){const k=key(x);if(!m.has(k))m.set(k,[]);m.get(k).push(x)}return m};
 function delta(a,metric){let h=a.filter(x=>x.hit),c=a.filter(x=>!x.hit);return h.length&&c.length?avg(h.map(metric))-avg(c.map(metric)):null}
 function yearPairs(a,metric){return [...groups(a,x=>x.date.slice(0,4))].sort((a,b)=>a[0].localeCompare(b[0])).map(([year,x])=>({year,delta:delta(x,metric)})).filter(x=>x.delta!==null)}
 function boot(pairs){if(pairs.length<5)return null;let seed=20261128;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
  let vals=[];for(let b=0;b<10000;b++){let s=0;for(let i=0;i<pairs.length;i++)s+=pairs[Math.floor(random()*pairs.length)].delta;vals.push(s/pairs.length)}vals.sort((a,b)=>a-b);return [quant(vals,.025),quant(vals,.975)]}
 function stats(a,metric){let pairs=yearPairs(a,metric),assets=[...new Set(a.map(x=>x.asset))],loo=assets.map(k=>delta(a.filter(x=>x.asset!==k),metric)).filter(x=>x!==null);return {nEvent:a.filter(x=>x.hit).length,nControl:a.filter(x=>!x.hit).length,pooled:delta(a,metric),yearBalanced:avg(pairs.map(x=>x.delta)),matchedYears:pairs.length,yearClusterBootstrap95:boot(pairs),leaveOneAssetOutRange:loo.length?[Math.min(...loo),Math.max(...loo)]:null}}
 const out=[];
 for(let rule of rules){let a=rows.filter(x=>x.rule===rule&&x.out?.["60"]!=null),ret=x=>x.out["60"].r,risk=x=>Number(x.out["60"].hit);
  if(a.some(x=>!Number.isFinite(ret(x))||typeof x.out["60"].hit!=="boolean"||typeof x.hit!=="boolean"))throw Error("invalid ledger");
  out.push({rule,return:stats(a,ret),adverse10:stats(a,risk),costSensitivity:[0,.005,.01,.02].map(c=>({roundTripHaircut:c,pooledReturnDifference:delta(a,x=>(1+ret(x))/.995*(1-c)-1),eventMean:avg(a.filter(x=>x.hit).map(x=>(1+ret(x))/.995*(1-c)-1))})),timeDiagnostics:[["2001-2012",x=>x.date<"2013-01-01"],["2013+",x=>x.date>="2013-01-01"]].map(([label,f])=>({label,return:stats(a.filter(f),ret),adverse10:stats(a.filter(f),risk)}))});
 }
 return {status:"EXPLORATORY_NOT_VALIDATED",observations:rows.length,results:out,limitations:["Year-cluster resampling of paired year means only; ignores cross-year serial dependence and asset dependence across years, not confirmatory inference.","Leave-one-asset-out sensitivity is not a confidence interval.","Time split selected after prior results, not holdout.","Ledger from focused scanner, not verified imported Node CLI; fee sensitivity is uniform haircut only.","No market or sector benchmark, terminal outcomes or corporate-action certification."]};
}

const a=process.argv.slice(2);if(a.length!==4)throw Error("Usage: node transfer_diagnostics.mjs batch1.json batch2.json batch3.json output.json");const inputs=a.slice(0,3).map(path=>({path,bytes:readFileSync(path)}));const result=diagnostics(inputs.map(x=>JSON.parse(x.bytes)));result.inputs=inputs.map(x=>({path:x.path,sha256:createHash("sha256").update(x.bytes).digest("hex")}));writeFileSync(a[3],JSON.stringify(result,null,2)+"\n",{flag:"wx"});
