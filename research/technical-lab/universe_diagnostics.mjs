// Secondary diagnostics on immutable completed run; no changes to frozen rules.
import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
const args=process.argv.slice(2);if(args.length!==3)throw Error("Usage: node universe_diagnostics.mjs audit.json universe.json output.json");
const ab=readFileSync(args[0]),ub=readFileSync(args[1]),audit=JSON.parse(ab),u=JSON.parse(ub),sha=x=>createHash("sha256").update(x).digest("hex");
if(u.auditSha256!==sha(ab)||u.assets.length!==1299||audit.files.length!==1299||u.inventorySha256!==audit.inventorySha256)throw Error("provenance mismatch");
const mean=x=>x.length?x.reduce((s,z)=>s+z,0)/x.length:null;
function group(x,key){const m=new Map;for(const r of x){const k=key(r);if(!m.has(k))m.set(k,[]);m.get(k).push(r)}return m}
const counts=(x,key)=>Object.fromEntries([...group(x,key)].map(([k,v])=>[k,v.length]));
function delta(rows,metric){let h=rows.filter(x=>x.hit),c=rows.filter(x=>!x.hit);return h.length&&c.length?mean(h.map(metric))-mean(c.map(metric)):null}
function pairedYears(rows,metric){return [...group(rows,x=>x.date.slice(0,4))].sort((a,b)=>a[0].localeCompare(b[0])).map(([year,z])=>({year,delta:delta(z,metric)})).filter(x=>x.delta!==null)}
function blockCI(pairs){ // resample contiguous three-calendar-year blocks (not exact inference)
 if(pairs.length<8)return null;
 let state=20261128,random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296};
 const years=pairs.map(x=>Number(x.year)),by=new Map(pairs.map(x=>[Number(x.year),x.delta])),blocks=[];
 for(let y=years[0];y<=years.at(-1)-2;y++){let z=[y,y+1,y+2].filter(k=>by.has(k)).map(k=>by.get(k));if(z.length===3)blocks.push(z)}
 if(!blocks.length)return null;
 let boot=[];for(let j=0;j<10000;j++){let b=[];while(b.length<pairs.length)b.push(...blocks[Math.floor(random()*blocks.length)]);boot.push(mean(b.slice(0,pairs.length)))}boot.sort((a,b)=>a-b);
 return [boot[249],boot[9749]];
}
function stats(rows,metric){const years=pairedYears(rows,metric),assets=group(rows,x=>x.asset);let h=rows.filter(x=>x.hit),c=rows.filter(x=>!x.hit),hs=h.reduce((s,x)=>s+metric(x),0),cs=c.reduce((s,x)=>s+metric(x),0);const loo=[];
 for(const z of assets.values()){let a=z.filter(x=>x.hit),b=z.filter(x=>!x.hit);if(h.length>a.length&&c.length>b.length)loo.push((hs-a.reduce((s,x)=>s+metric(x),0))/(h.length-a.length)-(cs-b.reduce((s,x)=>s+metric(x),0))/(c.length-b.length))}
 return {nEvent:h.length,nControl:c.length,pooled:delta(rows,metric),yearBalanced:mean(years.map(x=>x.delta)),years:years.length,yearBlockBootstrap95:blockCI(years),leaveOneAssetOutRange:loo.length?[Math.min(...loo),Math.max(...loo)]:null};
}
function nonoverlap(rows){const all=[];for(const z of group(rows,x=>x.asset).values()){let last="";for(const r of z.slice().sort((a,b)=>a.date.localeCompare(b.date)||Number(b.hit)-Number(a.hit))){if(r.date>last){all.push(r);last=r.result.exitDate}}}return all}
const results=[];for(const cohort of ["PREVIOUSLY_VIEWED","EXPANSION","SECURITY_HOLDOUT"])for(const rule of ["Y_RECLAIM3","M_COMP_BREAK","M_SUPPORT100"]){
 const all=u.observations.filter(x=>x.group===cohort&&x.rule===rule&&x.h===60),complete=all.filter(x=>x.result),market=complete.filter(x=>Number.isFinite(x.marketExcess)),n=nonoverlap(complete);
 results.push({cohort,rule,censored:all.length-complete.length,return:stats(complete,x=>x.result.ret),marketExcess:stats(market,x=>x.marketExcess),risk:stats(complete,x=>+x.result.hit10),nonoverlap:{return:stats(n,x=>x.result.ret),marketExcess:stats(n.filter(x=>Number.isFinite(x.marketExcess)),x=>x.marketExcess),risk:stats(n,x=>+x.result.hit10)},regime:["ABOVE_SMA200","BELOW_SMA200"].map(regime=>{const z=market.filter(x=>x.marketRegime===regime);return {regime,n:z.length,marketExcessDelta:delta(z,x=>x.marketExcess),riskDelta:delta(z,x=>+x.result.hit10)}}),cost:[0,.005,.01,.02].map(fee=>({fee,eventMean:mean(complete.filter(x=>x.hit).map(x=>(1+x.result.ret)/.995*(1-fee)-1))}))});
}
const out={status:"EXPLORATORY_NOT_VALIDATED",auditSha256:sha(ab),universeSha256:sha(ub),auditCounts:counts(audit.files,x=>x.status),assetCounts:counts(u.assets,x=>x.status),errors:counts(u.assets.filter(x=>x.status==="ERROR"),x=>String(x.error).replace(/\d{4}-\d{2}-\d{2}/g,"DATE")),cohortCounts:counts(u.assets.filter(x=>x.status==="USED_EXPLORATORY"),x=>x.group),results,limitations:["Already viewed outcomes; no confirmatory inference. Three-year moving block bootstrap of year-balanced paired-year means only; missing years excluded and edge weighting imperfect. No full two-way dependence model.","Nonoverlap across event/control combined per asset, chronological, not matched causal controls.","Market comparison SPY price-adjusted proxy, no sector/PIT data or delisting terminal outcomes.","No promotion or parameter changes."]};
writeFileSync(args[2],JSON.stringify(out,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({auditCounts:out.auditCounts,assetCounts:out.assetCounts,errors:out.errors,cohortCounts:out.cohortCounts,primary:results.map(x=>({cohort:x.cohort,rule:x.rule,ret:x.return,market:x.marketExcess,risk:x.risk,nonoverlap:{ret:x.nonoverlap.return.pooled,market:x.nonoverlap.marketExcess.pooled,risk:x.nonoverlap.risk.pooled},regime:x.regime}))},null,2));
