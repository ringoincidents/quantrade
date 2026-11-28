// Standalone Node integration test, using synthetic fixtures only.
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {createHash} from "node:crypto";
import {execFileSync} from "node:child_process";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";
const root=mkdtempSync(join(tmpdir(),"qt-lab-"));
try{
 const runner=fileURLToPath(new URL("./batch.mjs",import.meta.url));
 const rows=Array.from({length:430},(_,i)=>{const date=new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10);return {date,p:i<220?100:i<250?80:i<280?85:100}});
 function asset(id,rs,factor){const csv="date,open,high,low,close\n"+rs.map(x=>[x.date,...Array(4).fill(x.p*factor)].join(",")).join("\n")+"\n";const path=join(root,id+".csv");writeFileSync(path,csv);return {asset:id,prices:{path,format:"canonical",source:"synthetic test",rights:"synthetic",basis:"synthetic",sha256:createHash("sha256").update(csv).digest("hex")}}}
 const a=asset("A",rows,1),b=asset("B",rows,2);
 const m={experimentId:"integration-fixture",from:rows[199].date,to:rows.at(-1).date,fee:.0025,assets:[a,b],variants:[{rule:"hold",mode:"now"},{rule:"P",mode:"5"}]};
 const path=join(root,"manifest.json"),out=join(root,"out");
 const run=(manifest,dir)=>{writeFileSync(path,JSON.stringify(manifest));return execFileSync(process.execPath,[runner,path,dir],{encoding:"utf8",stdio:["ignore","pipe","pipe"]})};
 run(m,out);const report=JSON.parse(readFileSync(join(out,"batch_report.json"),"utf8"));
 assert.equal(report.assets.length,2);assert.equal(report.portfolios.length,2);
 assert.equal(report.assets[0].snapshot.date,m.to);
 for(const p of report.portfolios){const single=report.assets[0].results.find(r=>r.rule===p.rule&&r.mode===p.mode);assert.ok(Math.abs(single.metrics.totalReturn-p.metrics.totalReturn)<1e-10);assert.equal(p.metrics.orders,2*single.metrics.orders)}
 assert.throws(()=>run(m,out)); // exclusive output
 const wrong=asset("C",rows.filter((_,i)=>i!==300),1);assert.throws(()=>run({...m,assets:[a,wrong]},join(root,"bad-calendar")));
 assert.throws(()=>run({...m,assets:[{...a,prices:{...a.prices,sha256:"0".repeat(64)}}]},join(root,"bad-hash")));
 assert.throws(()=>run({...m,to:"2025-01-01"},join(root,"bad-end")));
 console.log("Synthetic batch CLI integration checks passed");
}finally{rmSync(root,{recursive:true,force:true})}
