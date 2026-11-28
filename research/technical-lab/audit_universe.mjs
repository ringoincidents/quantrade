import {readFileSync,writeFileSync,statSync} from "node:fs";
import {resolve} from "node:path";
import {createHash} from "node:crypto";
// Offline Lab inventory audit; no network, no price repair, no trading authority.
function auditCsv(text){
 const lines=text.trimEnd().split(/\r?\n/),errors=[],jumps=[],symbols=new Set();let first=null,last=null,previous=null;
 if(lines[0]!=="date,symbol,open,high,low,close,volume")return {rows:0,errors:[{reason:"HEADER"}],jumps,first,last,symbols:[]};
 for(let i=1;i<lines.length;i++){
  const z=lines[i].split(","),[d,s,...v]=z;let nums=v.map(Number),[o,h,l,c,vol]=nums;
  const t=new Date(d+"T00:00:00Z"),validDate=/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(t.getTime())&&t.toISOString().slice(0,10)===d;
  if(z.length!==7||!s||!validDate||last!==null&&d<=last||v.some(x=>x.trim()==="")||nums.some(x=>!Number.isFinite(x))||[o,h,l,c].some(x=>x<=0)||vol<0||h<l||h+1e-4<Math.max(o,c)||l-1e-4>Math.min(o,c)){errors.push({line:i+1,date:d,reason:"SCHEMA_DATE_OR_OHLCV"});previous=null;continue}
  first??=d;symbols.add(s);
  if(previous!==null&&Math.abs(c/previous.close-1)>.35)jumps.push({date:d,previousDate:previous.date,ratio:c/previous.close,classification:"UNRESOLVED_EXTREME_MOVE"});
  last=d;previous={date:d,close:c};
 }
 return {rows:lines.length-1,errors,jumps,first,last,symbols:[...symbols]};
}
function classify(quality,hashMatch,bytesMatch){
 if(!hashMatch||!bytesMatch)return "SNAPSHOT_MISMATCH";
 if(quality.errors.length)return "INVALID_PRICE_SHAPE";
 if(quality.jumps.length)return "REVIEW_EXTREME_MOVE";
 if(quality.rows<200)return "SHORT_HISTORY";
 return "PRICE_SHAPE_PASS_NOT_G0";
}
function selfTest(){
 const h="date,symbol,open,high,low,close,volume\n",row=(d,p)=>d+",A,"+[p,p,p,p,1].join(",");
 const a=auditCsv(h+row("2020-01-02",100)+"\n"+row("2020-01-03",50));
 if(a.jumps.length!==1||a.jumps[0].ratio!==.5||classify(a,true,true)!=="REVIEW_EXTREME_MOVE")throw Error("extreme move retained");
 if(classify(a,false,true)!=="SNAPSHOT_MISMATCH")throw Error("hash precedence");
 if(auditCsv(h+row("2020-02-30",100)).errors.length!==1)throw Error("invalid date");
 if(auditCsv(h+row("2020-01-02",100)+"\n"+row("2020-01-02",100)).errors.length!==1)throw Error("duplicate date");
 if(auditCsv(h+"2020-01-02,A,100,99,100,100,1").errors.length!==1)throw Error("bad OHLC");
 if(auditCsv(h+"2020-01-02,A,100,101,99,100,").errors.length!==1)throw Error("missing volume");
 if(classify(auditCsv(h+row("2020-01-02",100)),true,true)!=="SHORT_HISTORY")throw Error("short history");
 return 7;
}

const args=process.argv.slice(2);
if(args[0]==="--self-test"){console.log(JSON.stringify({assertions:selfTest()}));process.exit(0)}
if(args.length!==3)throw Error("Usage: node audit_universe.mjs source_inventory.json source-repo-root output.json");
const invBytes=readFileSync(args[0]),inv=JSON.parse(invBytes),sha=x=>createHash("sha256").update(x).digest("hex");
if(!Array.isArray(inv.files)||inv.files.length!==1299||new Set(inv.files.map(x=>x.path)).size!==1299)throw Error("invalid inventory");
const report={status:"EXPLORATORY_NOT_VALIDATED",inventorySha256:sha(invBytes),codeSha256:sha(readFileSync(new URL(import.meta.url))),source:inv.source,files:[]};
for(const f of inv.files){
 if(!/^data\/processed\/daily\/equities\/[^/]+\.csv$/.test(f.path)||!(/^[a-f0-9]{64}$/.test(f.sha256)))throw Error("invalid inventory path/hash");
 try{
  const path=resolve(args[1],f.path),bytes=readFileSync(path),hash=sha(bytes),quality=auditCsv(bytes.toString("utf8"));
  report.files.push({path:f.path,expectedSha256:f.sha256,actualSha256:hash,bytes:bytes.length,status:classify(quality,hash===f.sha256,bytes.length===f.bytes),...quality});
 }catch(e){report.files.push({path:f.path,status:e.code==="ENOENT"?"MISSING":"READ_ERROR",error:String(e)})}
}
report.counts=Object.fromEntries([...new Set(report.files.map(x=>x.status))].sort().map(s=>[s,report.files.filter(x=>x.status===s).length]));
report.limitations=["No automatic corporate-action adjustment, deletion or smoothing; extreme moves retained in audit ledger and quarantined for independent evidence.","No exchange calendar, PIT membership, delisting payout, merger consideration, split/dividend adjustment or execution liquidity certification.","Price-shape pass is NOT G0 or investment approval."];
writeFileSync(args[2],JSON.stringify(report,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify(report.counts));
