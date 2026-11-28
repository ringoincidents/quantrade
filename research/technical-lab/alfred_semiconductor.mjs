// Bounded ALFRED snapshot adapter. No credentials, no storage or trading authority.
import {createHash} from "node:crypto";
import {CONTRACT,evaluate,periodNumber,periodLabel} from "./industry_activity.mjs";
const IDS=["IPG3344S","CAPUTLG3344S"];
const FIRST={"IPG3344S":"2015-02-18","CAPUTLG3344S":"2022-08-16"};
const sha=b=>createHash("sha256").update(b).digest("hex");
const day=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x;
function cutoff(vintage){if(!day(vintage))throw Error("invalid vintage date");return new Date(Date.parse(vintage)+2*86400000).toISOString()}
function urlFor(id,vintage){
 if(!IDS.includes(id)||!day(vintage)||vintage<FIRST[id])throw Error("unsupported vintage");
 const n=periodNumber(vintage.slice(0,7),"M"),u=new URL("https://alfred.stlouisfed.org/graph/alfredgraph.csv");
 for(const [k,v] of Object.entries({id,vintage_date:vintage,revision_date:vintage,cosd:periodLabel(n-24,"M")+"-01",coed:vintage.slice(0,7)+"-01"}))u.searchParams.set(k,v);
 return u.toString();
}
function parseSnapshot(bytes,id,vintage){
 urlFor(id,vintage);const lines=Buffer.from(bytes).toString("utf8").replace(/^\uFEFF/,"").trimEnd().split(/\r?\n/),head=lines.shift()?.split(",");
 if(head?.length!==2||!["observation_date","DATE"].includes(head[0])||head[1]!==id+"_"+vintage.replaceAll("-",""))throw Error("VINTAGE_HEADER_MISMATCH");
 const rows=[],missing=[];let prev="";
 for(const l of lines){const p=l.split(",");if(p.length!==2)throw Error("INVALID_CSV_ROW");const [d,v]=p;
  if(!day(d)||!d.endsWith("-01")||d<=prev||d.slice(0,7)>=vintage.slice(0,7))throw Error("INVALID_REFERENCE_MONTH");
  prev=d;
  if(v==="."||v===""){missing.push(d.slice(0,7));continue}
  if(!/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(v)||!Number.isFinite(+v)||+v<=0)throw Error("INVALID_VALUE");
  rows.push({period:d.slice(0,7),value:+v})
 }
 if(!rows.length)throw Error("NO_OBSERVATIONS");
 return {id,vintage,availabilityCutoff:cutoff(vintage),sha256:sha(bytes),rows,missing,sourceUrl:urlFor(id,vintage)};
}
function makeInput(pair,{capturedAt,review}){
 if(!Array.isArray(pair)||pair.length!==2||pair[0].id!==IDS[0]||pair[1].id!==IDS[1]||pair[0].vintage!==pair[1].vintage)throw Error("SINGLE_COMMON_VINTAGE_REQUIRED");
 const asOf=cutoff(pair[0].vintage);
 if(!review||review.rights!=="RESEARCH_ALLOWED"||review.status!=="VERIFIED"||typeof review.reviewer!=="string"||!review.reviewer.trim()||!/^([a-f0-9]{64})$/.test(review.evidenceSha256??"")||!Array.isArray(review.snapshotHashes)||review.snapshotHashes.length!==2||pair.some((s,i)=>s.sha256!==review.snapshotHashes[i]))throw Error("EXTERNAL_REVIEW_REQUIRED");
 if(!Number.isFinite(Date.parse(capturedAt))||Date.parse(capturedAt)<Date.parse(asOf))throw Error("CAPTURE_BEFORE_SAFE_CUTOFF");
 const metrics=CONTRACT.industries[0].metrics;
 return {contractVersion:CONTRACT.version,asOf,series:pair.map((s,i)=>{const m=metrics[i],e={status:"VERIFIED",rights:"RESEARCH_ALLOWED",source:m.source,evidenceSha256:s.sha256};return {...e,id:m.id,frequency:"M",unit:m.unit,capturedAt,observations:s.rows.map(r=>({...r,...e,knownAt:asOf}))}})};
}
// Probe is deliberately separate from verified evaluator: no synthetic attestation.
async function fetchSnapshot(id,vintage,fetcher=fetch){
 const response=await fetcher(urlFor(id,vintage),{redirect:"error",signal:AbortSignal.timeout(12000),headers:{"Accept":"text/csv","User-Agent":"QuanTrade-research-source-probe/0.1"}});
 if(response.status!==200)throw Error("HTTP_"+response.status);
 if(!/^(text\/csv|application\/(csv|octet-stream)|text\/plain)(;|$)/i.test(response.headers.get("content-type")??""))throw Error("UNEXPECTED_CONTENT_TYPE");
 const reader=response.body?.getReader();if(!reader)throw Error("EMPTY_BODY");
 let chunks=[],size=0;try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>262144)throw Error("BODY_TOO_LARGE");chunks.push(Buffer.from(value))}}finally{await reader.cancel().catch(()=>{})}
 return parseSnapshot(Buffer.concat(chunks),id,vintage);
}
function preview(pair){
 if(pair.length!==2||pair[0].id!==IDS[0]||pair[1].id!==IDS[1]||pair[0].vintage!==pair[1].vintage)throw Error("SINGLE_COMMON_VINTAGE_REQUIRED");
 const maps=pair.map(s=>new Map(s.rows.map(r=>[periodNumber(r.period,"M"),r.value]))),latest=maps.map(m=>Math.max(...m.keys())),n=Math.min(...latest),asOf=cutoff(pair[0].vintage),age=periodNumber(asOf.slice(0,7),"M")-n;
 if(age<0||age>3||Math.max(...latest)-n>3)return {status:"BLOCKED",reason:"STALE_OR_MISALIGNED_SERIES"};
 const metrics=maps.map((m,i)=>{let v=[n,n-12,n-3,n-15].map(x=>m.get(x));if(v.some(x=>x===undefined))return null;const change=(a,b)=>i===0?100*(a/b-1):a-b,growth=change(v[0],v[1]),previousGrowth=change(v[2],v[3]);return {id:IDS[i],growth,previousGrowth,acceleration:growth-previousGrowth}});
 if(metrics.some(x=>!x))return {status:"BLOCKED",reason:"EXACT_PERIOD_MISSING"};
 const sign=x=>Math.abs(x)<=1e-9?0:Math.sign(x);
 const same=xs=>xs.every(x=>x===xs[0])?xs[0]:0,g=same(metrics.map(x=>sign(x.growth))),a=same(metrics.map(x=>sign(x.acceleration)));
 const phase=g===1&&a===1?"EXPANSION_PROXY":g===1&&a===-1?"SLOWDOWN_PROXY":g===-1&&a===1?"RECOVERY_PROXY":g===-1&&a===-1?"CONTRACTION_PROXY":"MIXED_OR_FLAT";
 return {status:"SOURCE_PREVIEW_NOT_VERIFIED",phase,period:periodLabel(n,"M"),asOf,metrics};
}
export {IDS,cutoff,urlFor,parseSnapshot,makeInput,fetchSnapshot,preview,sha};
