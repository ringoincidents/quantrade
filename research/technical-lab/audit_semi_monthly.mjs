// Audit immutable monthly preview. No refitting or data retrieval.
import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
import assert from "node:assert/strict";
import {monthEnds,summarize} from "./semi_monthly_replay.mjs";
const args=process.argv.slice(2);if(args.length!==2)throw Error("Usage: node audit_semi_monthly.mjs source.json output.json");
const bytes=readFileSync(args[0]),r=JSON.parse(bytes);assert.deepEqual(r.schedule,monthEnds());assert.deepEqual(r.rows.map(x=>x.vintage),r.schedule);
assert.deepEqual(summarize(r.rows),r.summary);
const seen=new Set(),unique=[],repeated=[];
for(const row of r.rows){const p=row.activity.period;if(p&&seen.has(p)){repeated.push({vintage:row.vintage,period:p,phase:row.activity.phase});continue}if(p)seen.add(p);unique.push(row)}
const paired=r.rows.filter(x=>x.outcome.status==="PAIRED"),dedup=summarize(unique);
const signCounts={};for(const x of r.rows){const m=x.activity.metrics;if(!m)continue;const key=m.map(y=>[Math.sign(y.growth),Math.sign(y.acceleration)].join(",")).join("|");signCounts[key]=(signCounts[key]??0)+1}
const report={status:"EXPLORATORY_NOT_VALIDATED",sourceSha256:createHash("sha256").update(bytes).digest("hex"),sourceRun:r.runId,decisionCount:r.rows.length,classified:r.rows.filter(x=>["EXPANSION_PROXY","CONTRACTION_PROXY","RECOVERY_PROXY","SLOWDOWN_PROXY"].includes(x.activity.phase)).length,summary:r.summary,firstReferencePeriodOnly:dedup,repeated,quarterSpaced:r.quarterSpaced,signCounts,baselineIdentical:paired.every(x=>x.outcome.predicted===x.outcome.baseline),exceptions:r.rows.filter(x=>["MISSING","CENSORED"].includes(x.outcome.status)||x.activity.status==="BLOCKED").map(x=>({vintage:x.vintage,period:x.activity.period??null,reason:x.outcome.reason})),limitations:["Secondary descriptive audit after viewing results; earliest reference observation retained without optimizing outcomes.","No independent economic ground truth, no investment performance, no predictive edge."]};
writeFileSync(args[1],JSON.stringify(report,null,2)+"\n",{flag:"wx"});console.log(JSON.stringify(report,null,2));
