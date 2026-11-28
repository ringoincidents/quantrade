"""Research-only GDP forecast comparison. No investment authority."""
import math
import statistics
import json

def evaluate(actual, spf, iar, warmup=4):
    if not len(actual)==len(spf)==len(iar) or not 4<=warmup<len(actual):
        raise ValueError("Aligned series and at least four warmup observations required")
    if not all(math.isfinite(v) for series in (actual,spf,iar) for v in series):
        raise ValueError("Missing or nonfinite observation")
    rows=[]
    for i in range(warmup,len(actual)):
        h=actual[:i]; x=h[:-1]; y=h[1:]
        mx=statistics.mean(x); my=statistics.mean(y)
        slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/(sum((a-mx)**2 for a in x)+25)
        median=statistics.median(h[-4:])
        rows.append(dict(index=i,actual=actual[i],predictions={
            "SPF":spf[i],"IAR":iar[i],"Persistence":h[-1],
            "QT mean":statistics.mean(h),"QT median4":median,
            "QT AR1 ridge":my+slope*(h[-1]-mx),"QT blend":(spf[i]+median)/2}))
    return rows

def score(rows):
    if not rows: raise ValueError("Empty evaluation")
    result={}
    for key in rows[0]["predictions"]:
        e=[r["predictions"][key]-r["actual"] for r in rows]
        result[key]={"mae":statistics.mean(map(abs,e)),"rmse":math.sqrt(statistics.mean(v*v for v in e)),"bias":statistics.mean(e)}
    return result

def main():
    import sys
    with open(sys.argv[1],encoding="utf-8") as f: data=json.load(f)
    rows=evaluate(data["actual"],data["spf"],data["iar"])
    print(json.dumps({"status":"EXPLORATORY_NOT_VALIDATED","n":len(rows),"scores":score(rows)},indent=2))
if __name__=="__main__": main()
