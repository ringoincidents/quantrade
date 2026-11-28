// Research-only economic activity proxy. No order, forecast, allocation or price signal.
const CONTRACT={
 version:"QT-INDUSTRY-ACTIVITY-0.1",status:"EXPLORATORY_NOT_VALIDATED",
 industries:[
 {id:"US_SEMICONDUCTOR_COMPONENTS",frequency:"M",maxLagMonths:3,metrics:[{id:"SEMI_PRODUCTION",unit:"INDEX_SA",transform:"PCT",source:"Federal Reserve G.17 NAICS 3344",url:"https://fred.stlouisfed.org/data/IPG3344S"},{id:"SEMI_UTILIZATION",unit:"PERCENT_SA",transform:"PP",source:"Federal Reserve G.17 NAICS 3344",url:"https://fred.stlouisfed.org/series/CAPUTLG3344S"}],limits:"US production proxy, not global chips or AI demand; two related series, not independent."},
 {id:"US_PETROLEUM",frequency:"M",maxLagMonths:4,metrics:[{id:"PETROLEUM_PRODUCTS_SUPPLIED",unit:"KBPD",transform:"PCT",source:"EIA Petroleum Supply Monthly",url:"https://www.eia.gov/dnav/pet/pet_sum_snd_d_nus_mbblpd_m_cur.htm"},{id:"CRUDE_PRODUCTION",unit:"KBPD",transform:"PCT",source:"EIA Petroleum Supply Monthly",url:"https://www.eia.gov/petroleum/supply/monthly/"}],limits:"US volumes, not global energy, inventories, prices or producer margins."},
 {id:"US_POWER_INFRA_PROXY",frequency:"M",maxLagMonths:4,metrics:[{id:"ELECTRICITY_RETAIL_SALES",unit:"MWH",transform:"PCT",source:"EIA Electric Power Monthly",url:"https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_01"},{id:"POWER_CONSTRUCTION",unit:"NOMINAL_USD_NSA",transform:"PCT",source:"Census construction spending power category",url:"https://www.census.gov/construction/c30/data/index.html"}],limits:"Weather-sensitive electricity demand plus nominal spending; not grid equipment orders or real capex."},
 {id:"US_CONSTRUCTION_PROXY",frequency:"M",maxLagMonths:4,metrics:[{id:"HOUSING_STARTS",unit:"UNITS_SAAR",transform:"PCT",source:"Census New Residential Construction",url:"https://www.census.gov/economic-indicators/housing_starts"},{id:"TOTAL_CONSTRUCTION",unit:"NOMINAL_USD_NSA",transform:"PCT",source:"Census construction spending",url:"https://www.census.gov/construction/c30/data/index.html"}],limits:"Residential starts plus all-sector nominal spending; not nonresidential orders or real volume."},
 {id:"US_FDIC_BANKS",frequency:"Q",maxLagMonths:6,metrics:[{id:"BANK_LOANS",unit:"NOMINAL_USD",transform:"PCT",source:"FDIC Quarterly Banking Profile",url:"https://www.fdic.gov/quarterly-banking-profile"},{id:"BANK_ROA",unit:"PERCENT",transform:"PP",source:"FDIC Quarterly Banking Profile",url:"https://www.fdic.gov/quarterly-banking-profile"}],limits:"Insured US banks only; loan growth nominal, ROA affected by credit costs and one-offs; not whole financial sector."}
 ]};
const finite=x=>typeof x==="number"&&Number.isFinite(x);
const utc=x=>typeof x==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x.slice(0,10)?Date.parse(x):NaN;
const nonblank=x=>typeof x==="string"&&x.trim()!=="";
const evidence=x=>x?.status==="VERIFIED"&&x.rights==="RESEARCH_ALLOWED"&&nonblank(x.source)&&/^[a-f0-9]{64}$/.test(x.evidenceSha256??"");
function periodNumber(p,f){
 const m=(f==="M"?/^(\d{4})-(0[1-9]|1[0-2])$/:/^(\d{4})-Q([1-4])$/).exec(p??"");
 if(!m||+m[1]<1900||+m[1]>2200)throw Error("invalid period "+p);
 return +m[1]*(f==="M"?12:4)+ +m[2]-1;
}
function periodLabel(n,f){const k=f==="M"?12:4;return Math.floor(n/k)+"-"+(f==="M"?String(n%k+1).padStart(2,"0"):"Q"+(n%k+1))}
function endMonth(n,f){return f==="M"?n:Math.floor(n/4)*12+(n%4+1)*3-1}
function periodEnd(n,f){let m=endMonth(n,f);return Date.UTC(Math.floor(m/12),m%12+1,1)-1}
function evaluate(input){
 if(!input||!finite(utc(input.asOf))||!Array.isArray(input.series)||input.contractVersion!==CONTRACT.version)throw Error("invalid input/contract");
 const cutoff=utc(input.asOf),as=new Date(cutoff),month=as.getUTCFullYear()*12+as.getUTCMonth();
 const defs=new Map(CONTRACT.industries.flatMap(s=>s.metrics.map(m=>[m.id,{...m,frequency:s.frequency}])));
 const series=new Map();
 for(const s of input.series){
  const def=defs.get(s.id);
  if(!def||series.has(s.id)||s.frequency!==def.frequency||s.unit!==def.unit||s.source!==def.source||!evidence(s)||!finite(utc(s.capturedAt))||!Array.isArray(s.observations))throw Error("invalid series contract "+s.id);
  const by=new Map(),unique=new Set();
  for(const o of s.observations){
   const n=periodNumber(o.period,s.frequency),known=utc(o.knownAt);
   if(!finite(o.value)||!finite(known)||known<=periodEnd(n,s.frequency)||known>utc(s.capturedAt)||!evidence(o)||o.source!==s.source||def.transform==="PCT"&&o.value<=0)throw Error("invalid observation "+s.id);
   const key=n+"|"+known;if(unique.has(key))throw Error("duplicate vintage "+s.id);unique.add(key);
   if(known>cutoff)continue;
   const old=by.get(n);if(!old||utc(old.knownAt)<known)by.set(n,o);
  }
  series.set(s.id,by)
 }
 const out=[];
 for(const industry of CONTRACT.industries){
  const f=industry.frequency,year=f==="M"?12:4,step=f==="M"?3:1;
  const maps=industry.metrics.map(m=>series.get(m.id));
  if(maps.some(m=>!m||!m.size)){out.push({industry:industry.id,status:"BLOCKED",reason:"MISSING_ASOF_SERIES",limits:industry.limits});continue}
  const latest=maps.map(m=>Math.max(...m.keys())),common=Math.min(...latest);
  const age=month-endMonth(common,f);
  if(age<0||age>industry.maxLagMonths||Math.max(...latest)-common>step){out.push({industry:industry.id,status:"BLOCKED",reason:"STALE_OR_MISALIGNED_SERIES",period:periodLabel(common,f),ageMonths:age,limits:industry.limits});continue}
  const metrics=industry.metrics.map((m,i)=>{
   const nums=[common,common-year,common-step,common-step-year],obs=nums.map(n=>maps[i].get(n));
   if(obs.some(x=>!x))return {id:m.id,status:"BLOCKED",reason:"EXACT_PERIOD_MISSING",required:nums.map(n=>periodLabel(n,f))};
   const change=(a,b)=>m.transform==="PP"?a-b:100*(a/b-1);
   const growth=change(obs[0].value,obs[1].value),previousGrowth=change(obs[2].value,obs[3].value),acceleration=growth-previousGrowth;
   if(![growth,previousGrowth,acceleration].every(finite))return {id:m.id,status:"BLOCKED",reason:"NONFINITE_CALCULATION"};
   return {id:m.id,status:"DESCRIPTIVE",growth,previousGrowth,acceleration,unit:m.transform==="PP"?"pp":"percent",vintages:obs.map(o=>({period:o.period,knownAt:o.knownAt,value:o.value,evidenceSha256:o.evidenceSha256}))}
  });
  if(metrics.some(m=>m.status==="BLOCKED")){out.push({industry:industry.id,status:"BLOCKED",reason:"INSUFFICIENT_EXACT_HISTORY",period:periodLabel(common,f),metrics,limits:industry.limits});continue}
  const sign=x=>Math.abs(x)<=1e-9?0:Math.sign(x);
  const gs=metrics.map(x=>sign(x.growth)),ds=metrics.map(x=>sign(x.acceleration)),same=x=>x.every(v=>v===x[0])?x[0]:0;
  const g=same(gs),d=same(ds);
  const phase=g===1&&d===1?"EXPANSION_PROXY":g===1&&d===-1?"SLOWDOWN_PROXY":g===-1&&d===1?"RECOVERY_PROXY":g===-1&&d===-1?"CONTRACTION_PROXY":"MIXED_OR_FLAT";
  out.push({industry:industry.id,status:"DESCRIPTIVE_ONLY",phase,period:periodLabel(common,f),ageMonths:age,latestPeriods:latest.map(n=>periodLabel(n,f)),metrics,limits:industry.limits})
 }
 return {status:"EXPLORATORY_NOT_VALIDATED",contractVersion:CONTRACT.version,asOf:input.asOf,industries:out,limitations:["Heuristic activity labels only; no economic-cycle ground truth, forecast, trading or allocation authority.","US proxy scope, nominal quantities and related inputs; not independent evidence of demand, supply, or profit.","YoY signs and acceleration over three months or one quarter; all two inputs must agree; no weighted composite or tuning.","Evidence and knownAt are external attestations; no authentication of source or vintage correctness by this calculator. Exact periods only, no silent fallback or imputation."]};
}
export {CONTRACT,evaluate,periodNumber,periodLabel};
