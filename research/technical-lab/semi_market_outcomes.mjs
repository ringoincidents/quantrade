// Research-only 60-session outcome comparator; consumes externally reviewed data.
const HASH=/^[a-f0-9]{64}$/;
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const iso=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x.slice(0,10)?Date.parse(x):NaN;
const evidence=x=>x?.status==="VERIFIED"&&x.rights==="RESEARCH_ALLOWED"&&typeof x.source==="string"&&!!x.source.trim()&&HASH.test(x.evidenceSha256??"");
function compare(replay,input){
 if(replay.status!=="SOURCE_PREVIEW_NOT_VERIFIED"||!Array.isArray(replay.rows)||!Array.isArray(input.sessions)||!Array.isArray(input.series)||!evidence(input.calendarEvidence)||!finite(iso(input.asOf)))throw Error("invalid evidence bundle");
 if(!["SOXX","SMH"].includes(input.sectorId)||input.marketId!=="SPY")throw Error("unsupported benchmark pair");
 const asOf=iso(input.asOf),sessions=input.sessions,idx=new Map();let prev="";
 for(const s of sessions){if(typeof s.date!=="string"||s.date<=prev||!finite(iso(s.openAt))||!finite(iso(s.closeAt))||s.openAt.slice(0,10)!==s.date||s.closeAt.slice(0,10)!==s.date||iso(s.openAt)>=iso(s.closeAt))throw Error("invalid session");idx.set(s.date,s);prev=s.date}
 if(!sessions.length)throw Error("empty calendar");
 const series=new Map();
 for(const s of input.series){
  if(![input.sectorId,input.marketId].includes(s.id)||series.has(s.id)||s.currency!=="USD"||s.basis!=="TOTAL_RETURN_ADJUSTED_PROXY"||!evidence(s)||!finite(iso(s.capturedAt))||!Array.isArray(s.bars))throw Error("invalid price series");
  const bars=new Map();
  for(const b of s.bars){let session=idx.get(b.date);if(!session||bars.has(b.date)||!finite(b.open)||!finite(b.close)||b.open<=0||b.close<=0||!finite(iso(b.knownAt))||iso(b.knownAt)<iso(session.closeAt)||iso(b.knownAt)>iso(s.capturedAt))throw Error("invalid bar");bars.set(b.date,b)}
  series.set(s.id,bars)
 }
 const rows=[],seen=new Set();let prevCutoff=-Infinity;
 for(const r of replay.rows){
  const phase=r.activity?.phase??"BLOCKED",cutoff=iso(r.activity?.asOf);
  const base={vintage:r.vintage,period:r.activity?.period??null,phase},block=reason=>rows.push({...base,status:"BLOCKED",reason});
  if(!finite(cutoff)||r.activity.status!=="SOURCE_PREVIEW_NOT_VERIFIED"){block("ACTIVITY_UNAVAILABLE");continue}
  if(cutoff<=prevCutoff)throw Error("unordered activity cutoffs");prevCutoff=cutoff;
  if(!["EXPANSION_PROXY","RECOVERY_PROXY","SLOWDOWN_PROXY","CONTRACTION_PROXY","MIXED_OR_FLAT"].includes(phase))throw Error("invalid phase");
  const duplicate=seen.has(base.period);seen.add(base.period);
  if(!series.has(input.sectorId)||!series.has(input.marketId)){block("BENCHMARK_UNAVAILABLE");continue}
  // No use of a first available bar if reference-calendar coverage begins after cutoff.
  if(iso(sessions[0].openAt)>cutoff){block("CALENDAR_START_UNCERTAIN");continue}
  const en=sessions.findIndex(s=>iso(s.openAt)>cutoff),ex=en+59;
  if(en<0||ex>=sessions.length||iso(sessions[ex].closeAt)>asOf){block("CENSORED_OR_CALENDAR_END");continue}
  const window=sessions.slice(en,ex+1);
  const values=[input.sectorId,input.marketId].map(id=>window.map(s=>series.get(id).get(s.date)));
  if(values.some(v=>v.some(b=>!b||iso(b.knownAt)>asOf))){block("MISSING_OR_NOT_KNOWN_BAR");continue}
  const ret=v=>v.at(-1).close/v[0].open*.995-1;
  const sector=ret(values[0]),market=ret(values[1]);if(!finite(sector)||!finite(market)){block("NONFINITE_RETURN");continue}
  rows.push({...base,status:"EXPLORATORY_MATCH",duplicateReference:duplicate,entry:window[0].date,exit:window.at(-1).date,sectorReturn:sector,marketReturn:market,excess:sector-market})
 }
 const summarize=z=>{
  const groups=new Map();
  for(const r of z){let g=groups.get(r.phase)??{phase:r.phase,eligible:0,matched:0,sum:0,positive:0,blocked:{}};g.eligible++;
   if(r.status==="EXPLORATORY_MATCH"){g.matched++;g.sum+=r.excess;g.positive+=+(r.excess>0)}else g.blocked[r.reason]=(g.blocked[r.reason]??0)+1;groups.set(r.phase,g)}
  return [...groups.values()].map(({sum,...g})=>({...g,meanExcess:g.matched?sum/g.matched:null}))
 };
 const nonoverlap=[];let last="";for(const r of rows)if(r.status==="EXPLORATORY_MATCH"&&r.entry>last){nonoverlap.push(r);last=r.exit}
 return {status:"EXPLORATORY_NOT_VALIDATED",sectorId:input.sectorId,marketId:input.marketId,asOf:input.asOf,rows,summary:summarize(rows),nonoverlap:summarize(nonoverlap),limitations:["Activity input is unverified source preview, price evidence declarations are not independently authenticated.","60 sessions inclusive, first scheduled open strictly after conservative cutoff, uniform 0.5% roundtrip on both proxy returns.","Price basis is total-return-adjusted proxy; not actual trading prices or independent economic ground truth.","Repeated reference months and overlapping windows retained in primary; nonoverlap is secondary, not a randomized test.","No timing, allocation, trading or forecast approval."]};
}
export {compare};
