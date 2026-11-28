// Lab-only completed-period features and equal-initial-capital sleeve aggregation.
function periodKey(d,tf){
 if(tf==="D")return d;
 if(tf==="M")return d.slice(0,7);
 if(tf==="Y")return d.slice(0,4);
 if(tf==="W"){let x=new Date(d+"T00:00Z");x.setUTCDate(x.getUTCDate()-((x.getUTCDay()+6)%7));return x.toISOString().slice(0,10)}
 throw Error("unsupported timeframe");
}

function periods(tf){return {D:[5,10,20,60,120,200,240,480,720,960],W:[5,10,20,40,60],M:[5,10,20,30,40,60,100,120],Y:[2,3,5,10]}[tf]}

function makeState(tf){return {tf,key:null,active:null,first:true,completed:[],sum:[0],snap:null}}

function updatePeriod(s,x){
 let key=periodKey(x.d,s.tf);
 if(s.tf==="D"){appendBar(s,{key,first:x.d,last:x.d,knownOn:x.d,o:x.o,h:x.h,l:x.l,p:x.p,sessions:1});return s.snap}
 if(key!==s.key){
  // First bucket may be truncated at input start. Never use it.
  if(s.active&&!s.first)appendBar(s,{...s.active,knownOn:x.d});
  if(s.active)s.first=false;
  s.key=key;s.active={key,first:x.d,last:x.d,o:x.o,h:x.h,l:x.l,p:x.p,sessions:1};
 }else{s.active.last=x.d;s.active.h=Math.max(s.active.h,x.h);s.active.l=Math.min(s.active.l,x.l);s.active.p=x.p;s.active.sessions++}
 return s.snap;
}

function appendBar(s,b){
 s.completed.push(b);s.sum.push(s.sum.at(-1)+b.p);
 let n=s.completed.length,ma={},slope={};
 for(let k of periods(s.tf)){ma[k]=n>=k?(s.sum[n]-s.sum[n-k])/k:null;slope[k]=n>k?(b.p-s.completed[n-k-1].p)/k:null}
 let cluster=s.tf==="D"?[5,10,20,60,120]:s.tf==="M"?[5,10,20,30,40,60]:null;
 let cv=null;
 if(cluster&&cluster.every(k=>ma[k]!==null)){let z=cluster.map(k=>ma[k]),m=z.reduce((a,b)=>a+b,0)/z.length;cv=Math.sqrt(z.reduce((a,b)=>a+(b-m)**2,0)/z.length)/m}
 let support={};if(s.tf==="M")for(let k of [60,100,120])support[k]=ma[k]===null?null:b.p/ma[k]-1;
 s.snap={bar:b,count:n,ma,slope,cv,support};
}

function multiTimeframe(rows){
 let states=["D","W","M","Y"].map(makeState);
 return rows.map(x=>({date:x.d,frames:Object.fromEntries(states.map(s=>[s.tf,updatePeriod(s,x)]))}));
}

function aggregateSleeves(sleeves){
 if(!sleeves.length)throw Error("empty sleeves");
 let first=sleeves[0].nav,ids=new Set();
 if(first.length<2)throw Error("insufficient portfolio observations");
 for(let s of sleeves){
  if(!s.asset||ids.has(s.asset))throw Error("duplicate or missing asset");ids.add(s.asset);
  if(s.nav.length!==first.length||s.nav.some((v,i)=>v.date!==first[i].date))throw Error("calendar mismatch: "+s.asset);
  if(s.nav.some(v=>!Number.isFinite(v.nav)||v.nav<=0||!Number.isFinite(v.equityWeight)||v.equityWeight< -1e-9||v.equityWeight>1+1e-9))throw Error("invalid sleeve NAV/weight");
 }
 let n=sleeves.length,nav=first.map((v,i)=>{let total=sleeves.reduce((z,s)=>z+s.nav[i].nav,0),equity=sleeves.reduce((z,s)=>z+s.nav[i].nav*s.nav[i].equityWeight,0);return {date:v.date,nav:total/n,equityWeight:equity/total}});
 let peak=1,mdd=0;for(let z of nav){peak=Math.max(peak,z.nav);mdd=Math.min(mdd,z.nav/peak-1)}
 let years=(new Date(nav.at(-1).date)-new Date(nav[0].date))/864e5/365.25;
 if(!(years>0))throw Error("invalid portfolio duration");
 let orderCount=sleeves.reduce((z,s)=>z+s.metrics.orders,0);
 return {metrics:{totalReturn:nav.at(-1).nav-1,cagr:nav.at(-1).nav**(1/years)-1,mdd,meanEquity:nav.reduce((z,v)=>z+v.equityWeight,0)/nav.length,orders:orderCount,meanSleeveTurnover:sleeves.reduce((z,s)=>z+s.metrics.turnover,0)/n,totalFeesInitialNAV:sleeves.reduce((z,s)=>z+s.metrics.totalFees,0)/n},nav};
}

function mtfSelfTest(){
 let n=0,check=(v,m)=>{if(!v)throw Error(m);n++},near=(a,b)=>Math.abs(a-b)<1e-9;
 let rows=Array.from({length:1500},(_,i)=>{let d=new Date(Date.UTC(2019,0,15+i)).toISOString().slice(0,10),p=100+i;return {d,o:p-.5,h:p+1,l:p-1,p}}).filter(x=>![0,6].includes(new Date(x.d).getUTCDay()));
 let m=multiTimeframe(rows),at=d=>m.find(x=>x.date===d);
 check(at("2019-02-01").frames.M===null,"first partial month excluded");
 let f=at("2019-03-01").frames.M;check(f.bar.key==="2019-02"&&f.bar.knownOn==="2019-03-01","completed month publication");
 check(f.bar.first==="2019-02-01"&&f.bar.last==="2019-02-28","month endpoints");
 let feb=rows.filter(x=>x.d.startsWith("2019-02"));check(f.bar.o===feb[0].o&&f.bar.h===Math.max(...feb.map(x=>x.h))&&f.bar.l===Math.min(...feb.map(x=>x.l))&&f.bar.p===feb.at(-1).p,"OHLC aggregation");
 check(at("2019-03-29").frames.M.bar.key==="2019-02","current month excluded");
 check(at("2020-01-01").frames.Y===null,"first partial year excluded");
 check(at("2021-01-01").frames.Y.bar.key==="2020","prior year only");
 check(at("2019-01-28").frames.W.bar.key==="2019-01-21","prior week only");
 check(m[3].frames.D.ma[5]===null,"warmup null");
 check(near(m[4].frames.D.ma[5],rows.slice(0,5).reduce((z,x)=>z+x.p,0)/5),"daily SMA");
 check(near(m[5].frames.D.slope[5],(rows[5].p-rows[0].p)/5),"SMA slope");
 check(m.at(-1).frames.M.ma[100]===null,"long monthly insufficient");
 check(m.at(-1).frames.M.cv===null,"compression warmup");
 for(let k of [100,300,700])check(JSON.stringify(multiTimeframe(rows.slice(0,k)))===JSON.stringify(m.slice(0,k)),"prefix invariance "+k);
 check(m.every(x=>["W","M","Y"].every(t=>!x.frames[t]||x.frames[t].bar.key<periodKey(x.date,t)&&x.frames[t].bar.knownOn<=x.date)),"no partial higher timeframe");
 let a={asset:"A",nav:[{date:"2020-01-01",nav:1,equityWeight:1},{date:"2021-01-01",nav:2,equityWeight:1}],metrics:{orders:1,turnover:1,totalFees:0}},b={asset:"B",nav:[{date:"2020-01-01",nav:1,equityWeight:0},{date:"2021-01-01",nav:1,equityWeight:0}],metrics:{orders:0,turnover:0,totalFees:0}};
 let c=aggregateSleeves([a,b]);check(near(c.metrics.totalReturn,.5),"independent equal initial sleeves");check(near(c.nav[1].equityWeight,2/3),"NAV-weighted exposure");
 let rejected=false;try{aggregateSleeves([a,{...b,nav:[b.nav[0],{...b.nav[1],date:"2021-01-02"}]}])}catch{rejected=true}check(rejected,"calendar mismatch rejected");
 rejected=false;try{aggregateSleeves([a,a])}catch{rejected=true}check(rejected,"duplicate assets rejected");
 return n;
}
export {multiTimeframe,aggregateSleeves,mtfSelfTest};
