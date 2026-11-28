// Bounded public-source feasibility probe; no raw data storage and no secrets.
import {IDS,fetchSnapshot,preview} from "./alfred_semiconductor.mjs";
const vintages=["2023-12-29","2025-12-31","2026-11-24"],results=[];
for(const vintage of vintages){
 const pair=[],sources=[];
 for(const id of IDS){
  try{const s=await fetchSnapshot(id,vintage);pair.push(s);sources.push({id,status:"PASS_SCHEMA",rows:s.rows.length,missing:s.missing.length,first:s.rows[0].period,last:s.rows.at(-1).period,sha256:s.sha256})}
  catch(e){const msg=String(e?.message??"");const safe=/^(HTTP_\d{3}|UNEXPECTED_CONTENT_TYPE|EMPTY_BODY|BODY_TOO_LARGE|VINTAGE_HEADER_MISMATCH|INVALID_CSV_ROW|INVALID_REFERENCE_MONTH|INVALID_VALUE|NO_OBSERVATIONS)$/.test(msg)?msg:e?.name==="TimeoutError"?"TIMEOUT":"TRANSPORT_OR_PARSE_ERROR";sources.push({id,status:"BLOCKED",reason:safe})}
 }
 results.push({vintage,sources,activity:pair.length===2?preview(pair):{status:"BLOCKED",reason:"INCOMPLETE_PAIR"}});
}
console.log(JSON.stringify({status:"SOURCE_FEASIBILITY_ONLY",results},null,2));
if(results.some(r=>r.sources.some(s=>s.status!=="PASS_SCHEMA")))process.exitCode=2;
