import {collect} from "./semi_monthly_replay.mjs";
const r=await collect();
console.log(JSON.stringify(r,null,2));
if(r.rows.some(x=>x.sources.some(s=>s.status!=="PASS_SCHEMA")))process.exitCode=2;
