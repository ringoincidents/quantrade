// Frozen exploratory schedule; no trading, credential or production authority.
import {periodNumber,periodLabel} from "./industry_activity.mjs";
import {IDS,fetchSnapshot,preview,cutoff} from "./alfred_semiconductor.mjs";
const START="2022-08",END="2026-10";
function monthEnds(){let a=[];for(let n=periodNumber(START,"M");n<=periodNumber(END,"M");n++){let m=periodLabel(n,"M"),[y,k]=m.split("-").map(Number);a.push(new Date(Date.UTC(y,k,0)).toISOString().slice(0,10))}return a}
const signs={EXPANSION_PROXY:1,RECOVERY_PROXY:1,SLOWDOWN_PROXY:-1,CONTRACTION_PROXY:-1};
const sign=x=>Math.abs(x)<=1e-9?0:Math.sign(x);
function outcome(current,later){
 const phase=current.activity?.phase;
 if(!signs[phase])return {status:"ABSTAIN",reason:current.activity?.reason??"MIXED_OR_UNAVAILABLE"};
 if(!later)return {status:"CENSORED",reason:"FUTURE_VINTAGE_OUTSIDE_SCHEDULE"};
 if(later.sources?.some(x=>x.status!=="PASS_SCHEMA")||!later.production)return {status:"MISSING",reason:"FUTURE_VINTAGE_UNAVAILABLE"};
 const n=periodNumber(current.activity.period,"M"),m=new Map(later.production.map(r=>[periodNumber(r.period,"M"),r.value]));
 const v=[n+3,n-9,n,n-12].map(x=>m.get(x));
 if(v.some(x=>!Number.isFinite(x)||x<=0))return {status:"MISSING",reason:"FUTURE_EXACT_PERIOD_MISSING"};
 const g0=100*(v[2]/v[3]-1),g3=100*(v[0]/v[1]-1),observed=sign(g3-g0),predicted=signs[phase],baseline=sign(current.activity.metrics[0].acceleration);
 return {status:"PAIRED",target:periodLabel(n+3,"M"),futureVintage:later.vintage,observed,predicted,baseline,observedGrowthChange:g3-g0,correct:predicted===observed,baselineCorrect:baseline===observed};
}
function summarize(rows){
 const counts={};for(const r of rows){const s=r.outcome.status;counts[s]=(counts[s]??0)+1}
 const pairs=rows.filter(r=>r.outcome.status==="PAIRED"),byPhase={};
 for(const r of pairs){const k=r.activity.phase,v=byPhase[k]??={n:0,correct:0,baselineCorrect:0,observedUp:0,observedDown:0,observedFlat:0};v.n++;v.correct+=+r.outcome.correct;v.baselineCorrect+=+r.outcome.baselineCorrect;v[r.outcome.observed>0?"observedUp":r.outcome.observed<0?"observedDown":"observedFlat"]++}
 return {counts,paired:pairs.length,correct:pairs.filter(r=>r.outcome.correct).length,baselineCorrect:pairs.filter(r=>r.outcome.baselineCorrect).length,byPhase};
}
function finish(raw){
 const rows=raw.map((r,i)=>{const {production,...clean}=r;return {...clean,outcome:outcome(r,raw[i+3])}});
 const phases={};for(const r of rows){let k=r.activity.phase??"BLOCKED";phases[k]=(phases[k]??0)+1}
 const spaced=rows.filter(r=>[2,5,8,11].includes(+r.vintage.slice(5,7)));
 return {status:"SOURCE_PREVIEW_NOT_VERIFIED",schedule:monthEnds(),phaseCounts:phases,summary:summarize(rows),quarterSpaced:summarize(spaced),rows,limitations:["Not independent ground truth, overlaps production input; previously inspected snapshots.","At classified months baseline is mechanically identical by construction; cannot claim incremental predictive skill.","No sector stock prices, profit outcomes, authorized raw archive, trading or forecast authority."]};
}
async function collect(fetcher=fetchSnapshot,pause=()=>new Promise(r=>setTimeout(r,1000))){
 const raw=[];let failed=0,stop=null;
 for(const vintage of monthEnds()){
  if(stop){raw.push({vintage,sources:IDS.map(id=>({id,status:"BLOCKED",reason:stop})),activity:{status:"BLOCKED",reason:stop}});continue}
  const settled=await Promise.allSettled(IDS.map(id=>fetcher(id,vintage)));
  const sources=settled.map((s,i)=>{const id=IDS[i];if(s.status==="fulfilled"){let x=s.value;return {id,status:"PASS_SCHEMA",rows:x.rows.length,missing:x.missing.length,sha256:x.sha256}}const msg=String(s.reason?.message??"");return {id,status:"BLOCKED",reason:/^(HTTP_\d{3}|VINTAGE_HEADER_MISMATCH|INVALID_VALUE|INVALID_REFERENCE_MONTH|INVALID_CSV_ROW|NO_OBSERVATIONS|BODY_TOO_LARGE|UNEXPECTED_CONTENT_TYPE|EMPTY_BODY)$/.test(msg)?msg:s.reason?.name==="TimeoutError"?"TIMEOUT":"TRANSPORT_OR_PARSE_ERROR"}});
  const pair=settled.filter(s=>s.status==="fulfilled").map(s=>s.value);
  raw.push({vintage,sources,activity:pair.length===2?preview(pair):{status:"BLOCKED",reason:"INCOMPLETE_PAIR"},production:pair.length===2?pair[0].rows:undefined});
  if(sources.some(x=>["HTTP_403","HTTP_429","HTTP_401"].includes(x.reason)))stop="PROVIDER_ACCESS_OR_RATE_LIMIT_STOP";
  failed=pair.length===2?0:failed+1;if(failed>=3&&!stop)stop="CONSECUTIVE_FAILURE_STOP";
  if(!stop)await pause();
 }
 return finish(raw);
}
export {monthEnds,outcome,summarize,finish,collect};
