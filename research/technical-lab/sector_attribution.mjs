// Research-only comparator. No new indicator, timing rule, trading or forecast authority.
const RULES=new Set(["Y_RECLAIM3","M_COMP_BREAK","M_SUPPORT100"]);
const HORIZONS=[5,20,60,120],BASIS="TOTAL_RETURN_ADJUSTED_PROXY",FACTOR=.995;
const nonblank=x=>typeof x==="string"&&x.trim()!=="";
const validDate=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x;
const time=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/.test(x)&&validDate(x.slice(0,10))&&Number.isFinite(Date.parse(x))?Date.parse(x):NaN;
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const blocked=reason=>({status:"BLOCKED",reason});
function evidence(x){return x?.status==="VERIFIED"&&nonblank(x.source)&&/^[a-f0-9]{64}$/.test(x.evidenceSha256??"")&&x.rights==="RESEARCH_ALLOWED"}
function makeContext(input){
 if(!input||!Array.isArray(input.sessions)||!Array.isArray(input.mappings)||!Array.isArray(input.series)||!evidence(input.calendarEvidence))throw Error("missing reference evidence");
 const sessions=input.sessions,idx=new Map();
 for(let i=0;i<sessions.length;i++){let s=sessions[i];if(!validDate(s.date)||!finite(time(s.closeAt))||s.closeAt.slice(0,10)!==s.date||i&&s.date<=sessions[i-1].date)throw Error("invalid calendar");idx.set(s.date,i)}
 if(!sessions.length)throw Error("empty calendar");
 const mapping=new Map();
 for(const m of input.mappings){
  if(!nonblank(m.asset)||!nonblank(m.securityId)||!nonblank(m.sectorId)||!nonblank(m.benchmarkId)||!validDate(m.from)||!(m.to===null||validDate(m.to)&&m.to>m.from)||!finite(time(m.knownAt))||!evidence(m))throw Error("invalid/unverified PIT mapping");
  if(!mapping.has(m.asset))mapping.set(m.asset,[]);mapping.get(m.asset).push(m)
 }
 const series=new Map();
 for(const s of input.series){
  if(!nonblank(s.id)||series.has(s.id)||!["MARKET","SECTOR"].includes(s.kind)||s.currency!=="USD"||s.basis!==BASIS||!evidence(s)||!finite(time(s.capturedAt))||!Array.isArray(s.bars))throw Error("invalid benchmark contract");
  const bars=new Map();let prev="";
  for(const b of s.bars){
   if(!idx.has(b.date)||b.date<=prev||!finite(b.open)||!finite(b.close)||b.open<=0||b.close<=0||!finite(time(b.knownAt))||time(b.knownAt)<time(sessions[idx.get(b.date)].closeAt)||time(b.knownAt)>time(s.capturedAt))throw Error("invalid benchmark bar");
   bars.set(b.date,b);prev=b.date
  }
  series.set(s.id,{...s,bars})
 }
 return {sessions,idx,mapping,series};
}
function mappingAt(ctx,asset,date,cutoff){
 const candidates=(ctx.mapping.get(asset)??[]).filter(m=>m.from<=date&&(m.to===null||date<m.to)&&time(m.knownAt)<=cutoff);
 if(candidates.length!==1)return blocked(candidates.length?"PIT_MAPPING_CONFLICT":"PIT_MAPPING_MISSING");
 return {status:"OK",mapping:candidates[0]};
}
function completeWindow(ctx,s,start,end,cutoff){
 if(!s||start<0||end>=ctx.sessions.length||start>end)return null;
 const rows=[];
 for(let i=start;i<=end;i++){const b=s.bars.get(ctx.sessions[i].date);if(!b||time(b.knownAt)>cutoff)return null;rows.push(b)}
 return rows;
}
function attributeEvent(ctx,e,{marketId,asOf}){
 if(!RULES.has(e.rule)||!HORIZONS.includes(e.h)||!nonblank(e.asset)||typeof e.hit!=="boolean"||!finite(time(asOf)))throw Error("invalid event request");
 if(e.result===null)return blocked("CENSORED_UNRESOLVED");
 const i=ctx.idx.get(e.date),en=ctx.idx.get(e.result?.entryDate),ex=ctx.idx.get(e.result?.exitDate);
 if(i===undefined||en!==i+1||ex!==i+e.h)return blocked("REFERENCE_HORIZON_MISMATCH");
 if(!finite(e.result.ret)||e.result.ret< -1||!finite(e.marketRet)||e.marketRet< -1)return blocked("INVALID_OR_MISSING_ORIGINAL_RETURN");
 const cutoff=time(asOf),signal=time(ctx.sessions[i].closeAt);
 if(cutoff<time(ctx.sessions[ex].closeAt))return blocked("OUTCOME_NOT_YET_KNOWN");
 const m=mappingAt(ctx,e.asset,e.date,signal);if(m.status!=="OK")return m;
 const sec=ctx.series.get(m.mapping.benchmarkId),market=ctx.series.get(marketId);
 if(!sec||sec.kind!=="SECTOR"||!market||market.kind!=="MARKET"||sec.id===market.id)return blocked("BENCHMARK_MISSING_OR_WRONG_KIND");
 const sb=completeWindow(ctx,sec,en,ex,cutoff),mb=completeWindow(ctx,market,en,ex,cutoff);
 if(!sb||!mb)return blocked("BENCHMARK_WINDOW_INCOMPLETE_OR_UNAVAILABLE");
 const sectorReturn=sb.at(-1).close/sb[0].open*FACTOR-1,marketReturn=mb.at(-1).close/mb[0].open*FACTOR-1;
 if(Math.abs(marketReturn-e.marketRet)>1e-9)return blocked("ORIGINAL_MARKET_RETURN_MISMATCH");
 return {status:"EXPLORATORY_MATCH",securityId:m.mapping.securityId,sectorId:m.mapping.sectorId,sectorBenchmark:sec.id,stockReturn:e.result.ret,sectorReturn,marketReturn,stockVsMarket:e.result.ret-marketReturn,stockVsSector:e.result.ret-sectorReturn,sectorVsMarket:sectorReturn-marketReturn};
}
// Descriptive price-relative cycle context only. Not economic cycle or a timing signal.
function sectorContext(ctx,{sectorId,marketId,date,asOf}){
 const i=ctx.idx.get(date),cutoff=time(asOf);
 if(i===undefined||!finite(cutoff)||cutoff<time(ctx.sessions[i].closeAt))return blocked("SESSION_OR_CUTOFF_UNAVAILABLE");
 const sec=ctx.series.get(sectorId),market=ctx.series.get(marketId);
 if(sec?.kind!=="SECTOR"||market?.kind!=="MARKET")return blocked("BENCHMARK_MISSING_OR_WRONG_KIND");
 const windows=[20,60,120].map(h=>{
  const a=completeWindow(ctx,sec,i-h,i,cutoff),b=completeWindow(ctx,market,i-h,i,cutoff);
  if(!a||!b)return {h,status:"BLOCKED",reason:"BENCHMARK_WINDOW_INCOMPLETE_OR_UNAVAILABLE"};
  const sectorReturn=a.at(-1).close/a[0].close-1,marketReturn=b.at(-1).close/b[0].close-1;
  return {h,status:"DESCRIPTIVE",sectorReturn,marketReturn,relativeReturn:sectorReturn-marketReturn};
 });
 return {status:windows.every(x=>x.status==="DESCRIPTIVE")?"DESCRIPTIVE_ONLY":"PARTIAL_OR_BLOCKED",sectorId,date,windows};
}
export {makeContext,attributeEvent,sectorContext};
