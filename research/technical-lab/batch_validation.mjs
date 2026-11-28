function validateBatch(m){
 if(!m||typeof m.experimentId!=="string"||!m.experimentId.trim()||!Array.isArray(m.assets)||!m.assets.length||!Array.isArray(m.variants)||!m.variants.length||!Number.isFinite(m.fee)||m.fee<0||m.fee>=.1)throw Error("incomplete batch manifest");
 if(!/^\d{4}-\d{2}-\d{2}$/.test(m.from)||!/^\d{4}-\d{2}-\d{2}$/.test(m.to)||m.from>=m.to)throw Error("invalid batch range");
 let ids=new Set(),vids=new Set();
 for(let a of m.assets){if(typeof a.asset!=="string"||!a.asset.trim()||ids.has(a.asset)||!["canonical","legacy-spy","plainbacktest"].includes(a.prices?.format))throw Error("invalid or duplicate asset");ids.add(a.asset)}
 for(let v of m.variants){if(!["hold","50","70","70R","B","P","M","D","H1","H3","H5","GH5"].includes(v.rule)||!["now","5","week","asym"].includes(v.mode)||(!["P","M"].includes(v.rule)&&v.mode!=="now"))throw Error("invalid variant");let id=v.rule+":"+v.mode;if(vids.has(id))throw Error("duplicate variant");vids.add(id)}
 if(m.variants.some(v=>v.rule==="M")&&(!m.credit||!m.vix))throw Error("macro inputs required for M");
 if(m.variants.some(v=>v.rule==="GH5")&&!m.vix)throw Error("VIX input required for GH5");
}

function batchRange(rows,from,to){
 let start=rows.findIndex(x=>x.d===from),end=rows.findIndex(x=>x.d===to);
 if(start<199||end<=start)throw Error("exact start/end trading dates and 200-session warmup required");
 return {start,end,dates:rows.slice(start,end+1).map(x=>x.d)};
}

function assertSameDates(a,b){if(a.length!==b.length||a.some((x,i)=>x!==b[i]))throw Error("different trading calendars; do not forward fill or silently intersect")}

function batchSelfTest(){
 let n=0,check=(v,msg)=>{if(!v)throw Error(msg);n++},reject=(f,msg)=>{let failed=false;try{f()}catch{failed=true}check(failed,msg)};
 let m={experimentId:"fixture",from:"2020-01-01",to:"2021-01-01",fee:.0025,assets:[{asset:"A",prices:{format:"canonical"}}],variants:[{rule:"hold",mode:"now"}]};
 validateBatch(m);check(true,"valid");
 reject(()=>validateBatch({...m,assets:[...m.assets,...m.assets]}),"duplicate assets");
 reject(()=>validateBatch({...m,variants:[...m.variants,...m.variants]}),"duplicate rules");
 reject(()=>validateBatch({...m,variants:[{rule:"M",mode:"5"}]}),"missing macro");
 reject(()=>validateBatch({...m,variants:[{rule:"GH5",mode:"now"}]}),"missing VIX");
 reject(()=>validateBatch({...m,variants:[{rule:"hold",mode:"5"}]}),"mode");
 reject(()=>validateBatch({...m,fee:-1}),"fee");
 let rows=Array.from({length:300},(_,i)=>({d:new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10)}));let range=batchRange(rows,rows[199].d,rows[299].d);
 check(range.dates.length===101,"range");
 reject(()=>batchRange(rows,rows[198].d,rows[299].d),"warmup");
 reject(()=>batchRange(rows,rows[199].d,"2022-01-01"),"missing end");
 assertSameDates(range.dates,[...range.dates]);check(true,"same dates");
 reject(()=>assertSameDates(range.dates,range.dates.slice(1)),"calendar mismatch");
 return n;
}
export {validateBatch,batchRange,assertSameDates,batchSelfTest};
