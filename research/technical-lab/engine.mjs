// QuanTrade Lab only. No network, brokerage, credentials, or live signals.
function parsePrices(csv,format="canonical"){
 const lines=csv.trim().split(/\r?\n/);
 const start=format==="legacy-spy"?3:1;
 if(!["legacy-spy","plainbacktest","canonical"].includes(format))throw Error("unknown price format");
 if(format==="canonical"&&lines[0].trim()!=="date,open,high,low,close")throw Error("canonical header mismatch");
 if(format==="plainbacktest"&&lines[0].trim()!=="date,symbol,open,high,low,close,volume")throw Error("plainbacktest header mismatch");
 return lines.slice(start).map(line=>{let z=line.split(",");let [d,o,h,l,p]=format==="legacy-spy"?[z[0],z[4],z[2],z[3],z[1]]:format==="plainbacktest"?[z[0],z[2],z[3],z[4],z[5]]:z;return {d,o:Number(o),h:Number(h),l:Number(l),p:Number(p)}});
}

function parseMacro(csv,column){
 const lines=csv.trim().split(/\r?\n/),head=lines[0].split(","),j=head.indexOf(column);
 if(j<1)throw Error("macro column missing");
 const map=new Map();let prior="";
 for(const line of lines.slice(1)){let z=line.split(","),d=z[0];if(!/^\d{4}-\d{2}-\d{2}$/.test(d)||d<=prior)throw Error("macro date order/duplicate");prior=d;let s=z[j]?.trim();if(s&&s!=="."&&Number.isFinite(Number(s))&&Number(s)>0)map.set(d,Number(s))}
 return map;
}

function audit(a){
 if(!Array.isArray(a)||a.length<200)throw Error("at least 200 rows required");
 for(let i=0;i<a.length;i++){let x=a[i],date=new Date(x.d+"T00:00Z");if(!/^\d{4}-\d{2}-\d{2}$/.test(x.d)||!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==x.d||i&&x.d<=a[i-1].d)throw Error("date order/duplicate "+i);
 if(![x.o,x.h,x.l,x.p].every(v=>Number.isFinite(v)&&v>0)||x.h+1e-4<Math.max(x.o,x.p)||x.l-1e-4>Math.min(x.o,x.p)||x.h<x.l)throw Error("invalid OHLC "+x.d);
 if(i&&Math.abs(x.p/a[i-1].p-1)>.35)throw Error("gross price jump; audit adjustment "+x.d)}
 return {rows:a.length,first:a[0].d,last:a.at(-1).d};
}

function mean(x){return x.reduce((s,v)=>s+v,0)/x.length}

function features(a,vix=new Map(),credit=new Map()){
 let age=0;
 return a.map((x,i)=>{let ma=n=>i>=n-1?mean(a.slice(i-n+1,i+1).map(z=>z.p)):NaN;let sma=ma(60);age=x.p<sma?age+1:0;let c=credit.get(a[i-2]?.d),c20=credit.get(a[i-22]?.d),c60=credit.get(a[i-62]?.d),v=vix.get(a[i-2]?.d),v20=vix.get(a[i-22]?.d);let dd=i>=119?x.p/Math.max(...a.slice(i-119,i+1).map(z=>z.p))-1:NaN;return {ok:i>=199&&[c,c20,c60,v,v20].every(Number.isFinite),dd,m20:x.p>=ma(20),m60:x.p>=sma,m200:x.p>=ma(200),c,c20,c60,v,v20,gap:x.p/sma-1,age,neg:i>=60&&x.p<=a[i-60].p,deep:dd<=-.2,priorFear:vix.get(a[i-1]?.d)>=30,priorVixAvailable:Number.isFinite(vix.get(a[i-1]?.d))}});
}

function week(d){let z=new Date(d+"T00:00Z");z.setUTCDate(z.getUTCDate()-((z.getUTCDay()+6)%7));return z.toISOString().slice(0,10)}

function fill(cash,shares,open,target,fee){
 let equity=shares*open,nav=cash+equity,delta=(target*nav-equity)/(target*nav>=equity?1+target*fee:1-target*fee);
 if(Math.abs(delta)<1e-12)return {cash,shares,delta:0,feePaid:0,turnover:0};
 let feePaid=fee*Math.abs(delta);return {cash:cash-delta-feePaid,shares:shares+delta/open,delta,feePaid,turnover:Math.abs(delta)/nav};
}

function simulate(a,F,{rule="P",mode="5",from,to,fee=.0025}){
 if(!["hold","50","70","70R","B","P","M","D","H1","H3","H5","GH5"].includes(rule)||!["now","5","week","asym"].includes(mode)||!Number.isFinite(fee)||fee<0||fee>=.1)throw Error("invalid fixed variant or fee");
 if(!["P","M"].includes(rule)&&mode!=="now")throw Error("execution variant only applies to P/M");
 let start=a.findIndex(x=>x.d>=from),end=a.findLastIndex(x=>x.d<=to);
 if(start<199||end<=start||from>to)throw Error("insufficient 200-session warmup or dates");
 if(rule==="M"&&!F.slice(start,end+1).some(x=>x.ok))throw Error("macro coverage unavailable");
 if(rule==="GH5"&&!F.slice(start,end+1).some(x=>x.priorVixAvailable))throw Error("VIX coverage unavailable");
 let cash=1,shares=0,pending=rule==="50"?.5:rule==="70"||rule==="70R"?.7:1,last=pending,signalDate=null,crisis=false,orders=0,turnover=0,totalFees=0,nav=[],trades=[],proposal=null,streak=0,delayed=0,missing=0;
 for(let i=start;i<=end;i++){let x=a[i];
 if(pending!==null){let f=fill(cash,shares,x.o,pending,fee);cash=f.cash;shares=f.shares;if(f.delta){orders++;turnover+=f.turnover;totalFees+=f.feePaid;trades.push({signalDate,fillDate:x.d,target:pending,open:x.o,notional:f.delta,fee:f.feePaid})}pending=null}
 let value=cash+shares*x.p;nav.push({date:x.d,nav:value,equityWeight:shares*x.p/value,target:last});
 if(i===end)continue;
 if(rule==="70R"){if(x.d.slice(0,7)!==a[i+1].d.slice(0,7)){pending=.7;signalDate=x.d}continue}
 if(["hold","50","70"].includes(rule))continue;
 let f=F[i];if((rule==="M"&&!f.ok)||(rule==="GH5"&&!f.priorVixAvailable)){missing++;proposal=null;streak=0;continue}
 let target=last;
 if(["D","H1","H3","H5","GH5"].includes(rule)){let b={D:0,H1:.01,H3:.03,H5:.05,GH5:.05}[rule],gate=rule!=="GH5"||!f.m200&&a[i].p<mean(a.slice(i-199,i+1).map(z=>z.p))||f.priorFear;
 if(last===1&&gate&&f.gap< -b&&f.age<=20&&f.neg)target=0;else if(last===0&&(!gate||f.gap>=b||(f.age>20&&f.deep)))target=1;
 }else{
 if(f.dd<=-.15)crisis=true;target=1;
 if(crisis){let exit=f.m200&&f.dd>-.10;if(exit&&(rule!=="M"||f.c<=f.c60)){crisis=false;target=1}else if(rule==="B")target=0;else{target=!f.m20?.25:f.m60?.75:.5;if(rule==="M"){if(f.c>f.c20&&f.v>f.v20)target=Math.min(target,.25);if(f.c>6&&f.c>f.c60)target=Math.min(target,.5);if(exit)target=Math.min(target,.75)}}}
 }
 if(target===proposal)streak++;else{proposal=target;streak=1}
 if(target===last)continue;
 let execute=mode==="now"||(mode==="5"&&streak>=5)||(mode==="week"&&week(x.d)!==week(a[i+1].d))||(mode==="asym"&&(target<last||streak>=5));
 if(execute){pending=target;last=target;signalDate=x.d}else if(target<last)delayed++;
 }
 let peak=1,mdd=0;for(let x of nav){peak=Math.max(peak,x.nav);mdd=Math.min(mdd,x.nav/peak-1)}
 let years=(new Date(a[end].d)-new Date(a[start].d))/864e5/365.25;
 return {metrics:{totalReturn:nav.at(-1).nav-1,cagr:nav.at(-1).nav**(1/years)-1,mdd,meanEquity:mean(nav.map(x=>x.equityWeight)),orders,turnover,totalFees,delayedReductionDays:delayed,missingDecisionDays:missing},nav,trades};
}

function selfTest(){
 let count=0,check=(v,msg)=>{if(!v)throw Error(msg);count++},near=(a,b)=>Math.abs(a-b)<1e-10;
 let a=Array.from({length:430},(_,i)=>{let d=new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10),p=i<220?100:i<250?80:i<280?85:100;return {d,p,o:p,h:p,l:p}});
 check(audit(a).rows===430,"audit");let F=features(a),from=a[199].d,to=a.at(-1).d;
 let b=fill(1,0,10,.7,.0025);check(near(b.shares*10/(b.cash+b.shares*10),.7),"buy target");let c=fill(b.cash,b.shares,10,.25,.0025);check(near(c.shares*10/(c.cash+c.shares*10),.25),"sell target");check(near(c.cash+c.shares*10,b.cash+b.shares*10-c.feePaid),"self-financing");
 let hold=simulate(a,F,{rule:"hold",mode:"now",from,to});check(hold.metrics.orders===1,"hold count");check(near(hold.metrics.totalReturn,1/1.0025-1),"hold costs");
 let now=simulate(a,F,{rule:"P",mode:"now",from,to}),five=simulate(a,F,{rule:"P",mode:"5",from,to});
 check(now.trades[1].signalDate===a[220].d&&now.trades[1].fillDate===a[221].d,"next open");
 check(five.trades[1].signalDate===a[224].d&&five.trades[1].fillDate===a[225].d,"5 close persistence");
 check(five.metrics.delayedReductionDays>=4,"delay measured");
 let asym=simulate(a,F,{rule:"P",mode:"asym",from,to});check(asym.trades[1].fillDate===a[221].d,"asymmetric exit");
 let prefix=a.slice(0,270),prefixResult=simulate(prefix,features(prefix),{rule:"P",mode:"5",from,to:prefix.at(-1).d});check(prefixResult.nav.every((z,i)=>near(z.nav,five.nav[i].nav)),"prefix causality");
 let rejected=false;try{audit([...a.slice(0,-1),a.at(-2)])}catch{rejected=true}check(rejected,"duplicate rejected");
 rejected=false;try{simulate(a,F,{rule:"M",mode:"now",from,to})}catch{rejected=true}check(rejected,"missing macro rejected");
 check(parseMacro("DATE,CLOSE\n2020-01-01,\n2020-01-02,.\n2020-01-03,30","CLOSE").size===1,"missing macro not zero");
 check(near(parsePrices("date,open,high,low,close\n2020-01-01,10,11,9,10")[0].p,10),"canonical parser");
 return count;
}
export {parsePrices,parseMacro,audit,features,fill,simulate,selfTest};
