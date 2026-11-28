// Lab only: frozen QT-MAR-O event definitions. No trading signals or orders.
function ruleIds(){return ["D_COMP_BREAK","M_COMP_BREAK","M_SUPPORT100","D_HIGH252","D_MATURE","D_RECLAIM20","W_RECLAIM20","Y_RECLAIM3"]}

function eventScan(a,snapshots){
 if(a.length!==snapshots.length||a.some((x,i)=>x.d!==snapshots[i].date))throw Error("snapshot alignment");
 let out=[],age=0,monthly=[],weekly=[];
 const valid=x=>Number.isFinite(x),allAbove=(f,ks)=>!!f&&ks.every(k=>valid(f.ma[k])&&f.bar.p>f.ma[k]),ready=(f,ks)=>!!f&&ks.every(k=>valid(f.ma[k]));
 let dk=[5,10,20,60,120],mk=[5,10,20,30,40,60];
 for(let i=0;i<a.length;i++){
  let x=a[i],f=snapshots[i].frames,prev=i?snapshots[i-1].frames:{},d=f.D,pd=prev.D;
  age=valid(d.ma[60])&&x.p<d.ma[60]?age+1:0;
  const add=(rule,eligible,hit)=>{if(eligible)out.push({rule,index:i,date:x.d,hit:!!hit})};
  let dd=i>=119?x.p/Math.max(...a.slice(i-119,i+1).map(z=>z.p))-1:null;
  let recent=i>=20&&snapshots.slice(i-20,i).some(z=>valid(z.frames.D.cv)&&z.frames.D.cv<=.05);
  add("D_COMP_BREAK",ready(d,dk)&&ready(pd,dk)&&recent&&!allAbove(pd,dk),allAbove(d,dk));
  add("D_HIGH252",i>=252,i>=252&&x.p>Math.max(...a.slice(i-252,i).map(z=>z.p)));
  add("D_MATURE",i>=119&&valid(d.ma[60])&&age>0&&x.p<=a[i-60].p&&dd<=-.2,age===21);
  add("D_RECLAIM20",i>=119&&valid(d.ma[20])&&valid(pd?.ma[20])&&dd<=-.15&&pd.bar.p<pd.ma[20],x.p>=d.ma[20]);
  if(f.M?.bar.knownOn===x.d){
   let m=f.M,pm=monthly.at(-1),prior3=monthly.slice(-3);
   add("M_COMP_BREAK",ready(m,mk)&&ready(pm,mk)&&prior3.length===3&&prior3.every(z=>valid(z.cv)&&z.cv<=.05)&&!allAbove(pm,mk),allAbove(m,mk));
   let z=[...monthly.slice(-11),m],deep=z.length===12&&m.bar.p/Math.max(...z.map(y=>y.bar.p))-1<=-.2;
   let elig=deep&&pm&&valid(pm.ma[100])&&valid(pm.slope[100])&&pm.slope[100]>0&&m.bar.p<pm.bar.p&&pm.bar.p>pm.ma[100]*1.05;
   add("M_SUPPORT100",elig,elig&&Math.abs(m.bar.p/pm.ma[100]-1)<=.05);
   monthly.push(m);
  }
  if(f.W?.bar.knownOn===x.d){
   let w=f.W,pw=weekly.at(-1),z=weekly.slice(-52),deep=z.length===52&&pw.bar.p/Math.max(...z.map(y=>y.bar.p))-1<=-.15;
   add("W_RECLAIM20",deep&&valid(w.ma[20])&&valid(pw?.ma[20])&&pw.bar.p<pw.ma[20],w.bar.p>=w.ma[20]);weekly.push(w);
  }
  if(f.Y?.bar.knownOn===x.d){let y=f.Y,py=prev.Y;add("Y_RECLAIM3",valid(y.ma[3])&&valid(py?.ma[3])&&py.bar.p<py.ma[3],y.bar.p>=y.ma[3])}
 }
 return out;
}

function outcome(a,i,h,fee=.005){
 if(!Number.isInteger(h)||h<=0||!Number.isFinite(fee)||fee<0||fee>=1)throw Error("invalid horizon or cost");
 if(i+h>=a.length)return null;
 let z=a.slice(i+1,i+h+1),entry=z[0].o,low=Math.min(...z.map(x=>x.l)),high=Math.max(...z.map(x=>x.h));
 return {entryDate:z[0].d,exitDate:z.at(-1).d,ret:z.at(-1).p/entry*(1-fee)-1,mae:low/entry-1,mfe:high/entry-1,hit10:low/entry<=.9};
}

function eventOutcomes(a,events,{from,to,fee=.005}){
 const end=a.findLastIndex(x=>x.d<=to);if(end<0||from>to)throw Error("invalid dates");
 let rows=[];
 for(let e of events){if(e.date<from||e.date>to)continue;for(let h of [5,20,60,120])rows.push({...e,h,result:e.index+h<=end?outcome(a,e.index,h,fee):null})}
 return rows;
}

function selectNonoverlap(rows){
 let last=-1,selected=[];
 for(let x of rows.filter(x=>x.result).sort((a,b)=>a.index-b.index)){if(x.index>last){selected.push(x);last=x.index+x.h}}
 return selected;
}

function eventStats(rows){
 let m=rows.filter(x=>x.result),n=m.length;
 if(!n)return {n:0,censored:rows.length,mean:null,median:null,win:null,mae:null,mfe:null,hit10:null};
 let mean=f=>m.reduce((z,x)=>z+f(x.result),0)/n,rs=m.map(x=>x.result.ret).sort((a,b)=>a-b);
 return {n,censored:rows.length-n,mean:mean(x=>x.ret),median:(rs[(n-1)>>1]+rs[n>>1])/2,win:mean(x=>+(x.ret>0)),mae:mean(x=>x.mae),mfe:mean(x=>x.mfe),hit10:mean(x=>+x.hit10)};
}

function summarizeEvents(rows){
 let out=[];
 for(let rule of ruleIds())for(let h of [5,20,60,120])for(let hit of [true,false]){
 let z=rows.filter(x=>x.rule===rule&&x.h===h&&x.hit===hit);
 // Nonoverlap selection is separate per asset, so cross-asset dates remain correlated.
 let by=new Map();for(let x of z){let k=x.asset??"single";if(!by.has(k))by.set(k,[]);by.get(k).push(x)}
 let non=[...by.values()].flatMap(selectNonoverlap);
 out.push({rule,h,group:hit?"event":"eligible_non_event",all:eventStats(z),nonoverlap:eventStats(non)});
 }
 return out;
}

function eventSelfTest(){
 let n=0,check=(v,m)=>{if(!v)throw Error(m);n++},near=(a,b)=>Math.abs(a-b)<1e-10;
 let a=Array.from({length:400},(_,i)=>({d:new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10),o:100,h:101,l:99,p:100}));
 a[253]={...a[253],p:110,h:111};a[254]={...a[254],o:105,p:105,h:106,l:90};
 let snaps=a.map(x=>({date:x.d,frames:{D:{bar:x,ma:{},cv:null},W:null,M:null,Y:null}}));
 let e=eventScan(a,snaps);check(e.filter(x=>x.rule==="D_HIGH252"&&x.hit).length===1,"strict prior high");
 check(e.find(x=>x.rule==="D_HIGH252"&&x.hit).index===253,"high signal day");
 check(!e.some(x=>x.index<252),"warmup");
 let z=outcome(a,253,5);check(z.entryDate===a[254].d&&z.exitDate===a[258].d,"next open and horizon");
 check(near(z.ret,100/105*.995-1),"cost");check(near(z.mae,90/105-1)&&z.hit10,"adverse low");
 check(outcome(a,399,5)===null,"right censor");
 let rr=eventOutcomes(a,e,{from:a[253].d,to:a[255].d});check(rr.every(x=>x.result===null),"cutoff censor");
 let r=[0,5,6,12].map(i=>({index:i,h:5,result:z}));check(selectNonoverlap(r).map(x=>x.index).join(",")==="0,6,12","strict nonoverlap");
 check(eventStats([]).mean===null,"no observations null");
 check(eventStats([{result:null}]).censored===1,"censor count");
 let prefix=eventScan(a.slice(0,300),snaps.slice(0,300));check(JSON.stringify(prefix)===JSON.stringify(e.filter(x=>x.index<300)),"prefix invariance");
 let s=summarizeEvents([{rule:"D_HIGH252",h:5,hit:true,index:0,result:z,asset:"A"},{rule:"D_HIGH252",h:5,hit:true,index:0,result:z,asset:"B"}]).find(x=>x.rule==="D_HIGH252"&&x.h===5&&x.group==="event");check(s.nonoverlap.n===2,"asset separate");
 // Explicit completed-month fixture: prior 3 compressed and below all, current breaks above.
 let mrows=a.slice(0,5),mf=mrows.map((x,i)=>({date:x.d,frames:{D:{bar:x,ma:{},cv:null},W:null,Y:null,M:{bar:{p:i===4?110:90,knownOn:x.d},ma:Object.fromEntries([5,10,20,30,40,60].map(k=>[k,100])),cv:.01,slope:{}}}}));
 check(eventScan(mrows,mf).filter(x=>x.rule==="M_COMP_BREAK"&&x.hit).length===1,"monthly breakout");
 let later=[...mf,{date:a[5].d,frames:{...mf[4].frames,D:{bar:a[5],ma:{},cv:null}}}];check(eventScan(a.slice(0,6),later).filter(x=>x.rule==="M_COMP_BREAK"&&x.hit).length===1,"monthly dedup");
 // Frozen M_SUPPORT100: previous close is above the band, current close may enter it.
 const supportFixture=(current,previous)=>{let rr=a.slice(0,12);let ss=rr.map((x,i)=>({date:x.d,frames:{D:{bar:x,ma:{},cv:null},W:null,Y:null,M:{bar:{p:i===11?current:i===10?previous:140,knownOn:x.d},ma:{100:100},slope:{100:1},cv:null}}}));return eventScan(rr,ss).filter(x=>x.rule==="M_SUPPORT100"&&x.index===11)};
 let positive=supportFixture(100,120);check(positive.length===1&&positive[0].hit,"support current enters band from previous close");
 let control=supportFixture(90,120);check(control.length===1&&!control[0].hit,"support eligible non-event below band");
 check(supportFixture(100,104).length===0,"support previous close must exceed band");
 return n;
}
export {ruleIds,eventScan,outcome,eventOutcomes,selectNonoverlap,eventStats,summarizeEvents,eventSelfTest};
