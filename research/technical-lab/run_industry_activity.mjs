// Read-only offline CLI. Explicit expected input hash is required.
import {readFileSync,writeFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {CONTRACT,evaluate} from "./industry_activity.mjs";
const hash=b=>createHash("sha256").update(b).digest("hex");
const args=process.argv.slice(2);
if(args.length===1&&args[0]==="--contract"){console.log(JSON.stringify(CONTRACT,null,2));process.exit(0)}
if(args.length!==3)throw Error("Usage: node run_industry_activity.mjs input.json expected-sha256 output.json");
const bytes=readFileSync(args[0]);if(!/^[a-f0-9]{64}$/.test(args[1])||hash(bytes)!==args[1])throw Error("input hash mismatch");
const result=evaluate(JSON.parse(bytes));
const report={...result,inputSha256:hash(bytes),contractSha256:hash(JSON.stringify(CONTRACT)),codeSha256:Object.fromEntries(["industry_activity.mjs","run_industry_activity.mjs"].map(f=>[f,hash(readFileSync(new URL("./"+f,import.meta.url)))]))};
writeFileSync(args[2],JSON.stringify(report,null,2)+"\n",{flag:"wx"});
console.log(JSON.stringify({status:result.status,industries:result.industries.map(({industry,status,phase,reason,period})=>({industry,status,phase,reason,period}))}));
