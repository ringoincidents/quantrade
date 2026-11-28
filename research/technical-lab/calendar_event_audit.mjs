// Secondary calendar alignment audit; source-derived reference, not exchange attestation.
import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
const dateOk=d=>typeof d==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(d).toISOString().slice(0,10)===d;
function parseCalendar(text){
 const lines=text.trimEnd().split(/\r?\n/);if(lines.shift()!=="date,open_utc,close_utc,is_early_close")throw Error("calendar header");
 const dates=[],index=new Map;let prev="";
 for(const l of lines){const [d,o,c,early,...rest]=l.split(",");if(rest.length||!dateOk(d)||d<=prev||!["True","False"].includes(early)||!o?.endsWith("Z")||!c?.endsWith("Z")||!Number.isFinite(Date.parse(o))||!Number.isFinite(Date.parse(c))||Date.parse(o)>=Date.parse(c)||o.slice(0,10)!==d||c.slice(0,10)!==d)throw Error("invalid calendar row "+d);
  index.set(d,dates.length);dates.push(d);prev=d}
 if(!dates.length)throw Error("empty calendar");
 return {dates,index};
}
function eventWindow(e,cal){
 if(!dateOk(e.date)||![5,20,60,120].includes(e.h)||!["Y_RECLAIM3","M_COMP_BREAK","M_SUPPORT100"].includes(e.rule))throw Error("invalid event");
 const {dates,index}=cal,signal=index.get(e.date);
 if(signal===undefined)return {status:"SIGNAL_NOT_REFERENCE_SESSION"};
 const prefix=e.rule==="Y_RECLAIM3"?4:7;
 const publication=signal>0&&dates[signal-1].slice(0,prefix)!==e.date.slice(0,prefix)?"FIRST_REFERENCE_SESSION":signal===0?"UNKNOWN_CALENDAR_START":"LATER_REFERENCE_SESSION";
 if(e.result===null)return {status:"CENSORED_UNRESOLVED",publication};
 if(!e.result||!dateOk(e.result.entryDate)||!dateOk(e.result.exitDate)||!Number.isFinite(e.result.ret)||typeof e.result.hit10!=="boolean")throw Error("invalid outcome");
 const entry=index.get(e.result.entryDate),exit=index.get(e.result.exitDate);
 if(entry===undefined||exit===undefined)return {status:"ENDPOINT_NOT_REFERENCE_SESSION",publication};
 if(entry<=signal||exit<entry)return {status:"INVALID_CHRONOLOGY",publication};
 if(entry!==signal+1||exit!==signal+e.h)return {status:"REFERENCE_HORIZON_MISMATCH",publication,entryDelaySessions:entry-signal-1,exitDelaySessions:exit-signal-e.h};
 if(publication!=="FIRST_REFERENCE_SESSION")return {status:"PUBLICATION_DAY_NOT_FIRST",publication};
 return {status:"ENDPOINT_SCHEDULE_MATCH",publication};
}
function summarize(rows){const m=new Map;for(const r of rows){const key=[r.group,r.rule,r.h,r.hit,r.status].join("|");let v=m.get(key);if(!v){v={group:r.group,rule:r.rule,h:r.h,hit:r.hit,status:r.status,n:0,nReturn:0,returnSum:0,marketN:0,marketSum:0,riskSum:0};m.set(key,v)}v.n++;if(r.result){v.nReturn++;v.returnSum+=r.result.ret;v.riskSum+=Number(r.result.hit10);if(Number.isFinite(r.marketExcess)){v.marketN++;v.marketSum+=r.marketExcess}}}return [...m.values()].map(({returnSum,marketSum,riskSum,...v})=>({...v,meanReturn:v.nReturn?returnSum/v.nReturn:null,meanMarketExcess:v.marketN?marketSum/v.marketN:null,adverse10:v.nReturn?riskSum/v.nReturn:null}));}
function selfTest(){
 const h="date,open_utc,close_utc,is_early_close\n",ds=["2020-12-31","2021-01-04","2021-01-05","2021-01-06","2021-01-07","2021-01-08","2021-01-11","2021-01-12","2021-01-13"],line=d=>d+","+d+"T14:30:00Z,"+d+"T21:00:00Z,False";
 const cal=parseCalendar(h+ds.map(line).join("\n")),base={date:ds[1],rule:"Y_RECLAIM3",h:5,result:{entryDate:ds[2],exitDate:ds[6],ret:.1,hit10:false}},check=(ok,m)=>{if(!ok)throw Error(m)};
 check(eventWindow(base,cal).status==="ENDPOINT_SCHEDULE_MATCH","exact first day and horizon");
 check(eventWindow({...base,result:{...base.result,entryDate:ds[3],exitDate:ds[7]}},cal).status==="REFERENCE_HORIZON_MISMATCH","missing entry");
 check(eventWindow({...base,result:{...base.result,exitDate:ds[7]}},cal).exitDelaySessions===1,"extended horizon");
 check(eventWindow({...base,date:ds[2],result:{...base.result,entryDate:ds[3],exitDate:ds[7]}},cal).status==="PUBLICATION_DAY_NOT_FIRST","late publication");
 check(eventWindow({...base,result:null},cal).status==="CENSORED_UNRESOLVED","censor not fabricated");
 check(eventWindow({...base,date:"2021-01-02"},cal).status==="SIGNAL_NOT_REFERENCE_SESSION","weekend");
 check(eventWindow({...base,result:{...base.result,exitDate:"2021-01-10"}},cal).status==="ENDPOINT_NOT_REFERENCE_SESSION","weekend exit");
 check(eventWindow({...base,result:{...base.result,entryDate:ds[0]}},cal).status==="INVALID_CHRONOLOGY","backwards entry");
 let bad=false;try{parseCalendar(h+line(ds[0])+"\n"+line(ds[0]))}catch{bad=true}check(bad,"duplicate calendar session");
 check(eventWindow({...base,date:ds[0],result:{...base.result,entryDate:ds[1],exitDate:ds[5]}},cal).status==="PUBLICATION_DAY_NOT_FIRST","unknown first calendar period");
 const s=summarize([{...base,group:"A",hit:true,status:"ENDPOINT_SCHEDULE_MATCH",marketExcess:.02},{...base,group:"A",hit:true,status:"CENSORED_UNRESOLVED",result:null}]);check(s.length===2&&s[0].meanMarketExcess===.02&&s[1].meanReturn===null,"group and missing outcomes");
 return 11;
}

const args=process.argv.slice(2);if(args[0]==="--self-test"){console.log(JSON.stringify({assertions:selfTest()}));process.exit(0)}
if(args.length!==4)throw Error("Usage: node calendar_event_audit.mjs audit.json universe.json XNYS.csv output.json");
const ab=readFileSync(args[0]),ub=readFileSync(args[1]),cb=readFileSync(args[2]),a=JSON.parse(ab),u=JSON.parse(ub),sha=x=>createHash("sha256").update(x).digest("hex");
if(u.auditSha256!==sha(ab)||u.inventorySha256!==a.inventorySha256||u.assets.length!==1299||a.files.length!==1299)throw Error("artifact lineage mismatch");
if(sha(cb)!=="08551fe647c2e7cdc7aa7ae00df6aa0c3446e4bdef5c8b624a5797ad8a25eac9")throw Error("calendar snapshot hash mismatch");
const cal=parseCalendar(cb.toString("utf8"));if(cal.dates.length!==8558)throw Error("calendar count mismatch");
const rows=u.observations.map(e=>({...e,...eventWindow(e,cal)}));
const counts=Object.fromEntries([...new Set(rows.map(e=>e.status))].map(s=>[s,rows.filter(e=>e.status===s).length]));
const by=summarize(rows),out={status:"EXPLORATORY_NOT_VALIDATED",calendarBasis:"PlainBacktest XNYS exchange_calendars 4.13.2; source reference only",calendarSha256:sha(cb),auditSha256:sha(ab),universeSha256:sha(ub),codeSha256:sha(readFileSync(new URL(import.meta.url))),counts,summary:by,flagged:rows.filter(x=>!["ENDPOINT_SCHEDULE_MATCH","CENSORED_UNRESOLVED"].includes(x.status)).map(({asset,group,rule,h,date,hit,result,status,publication,entryDelaySessions,exitDelaySessions})=>({asset,group,rule,h,date,hit,entry:result?.entryDate??null,exit:result?.exitDate??null,status,publication,entryDelaySessions,exitDelaySessions})),limitations:["Checks reference session endpoints, not all intervening bars or signal lookback completeness; offsetting extra and missing observations can escape detection.","XNYS calendar from same data source; not independently attested for all securities or dates. No exchange-specific halt or terminal outcome validation.","Late publication may be conservative, not necessarily erroneous. No missing prices imputed and no historical results rewritten.","Strict endpoint subset is secondary exploratory diagnostic, not independent validation. No trading authority."]};
writeFileSync(args[3],JSON.stringify(out,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({counts,primary:by.filter(x=>x.h===60&&x.group==="SECURITY_HOLDOUT")},null,2));
