"""Render offline JSON replay output as a standalone HTML research report."""
import html
import json
import math
import sys

def render(report):
    if report["status"]!="RETROSPECTIVE_UNVERIFIED": raise ValueError("Unsupported report")
    def number(v):
        if v is None: return "N/A"
        if not math.isfinite(v): raise ValueError("Nonfinite metric")
        return format(v,".3f")
    rows=[]
    for m in report["scorecard"]["models"]:
        cells=[html.escape(m["model"]),html.escape(m["version"]),str(int(m["n"]))]+[number(m[k]) for k in ("mae","rmse","bias","skill")]
        rows.append("<tr>"+"".join("<td>"+c+"</td>" for c in cells)+"</tr>")
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>QuanTrade Research</title><style>body{font:16px system-ui;margin:24px auto;padding:0 16px;max-width:900px}h1{font-size:24px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{text-align:right;padding:10px;border-bottom:1px solid #aaa}td:first-child,th:first-child{text-align:left}.scroll{overflow-x:auto}</style><h1>QuanTrade / GDP Research</h1><p>RETROSPECTIVE UNVERIFIED — not a live forecast or trading signal.</p><p>Skill relative to persistence; N/A if baseline MAE is zero.</p><div class="scroll"><table><thead><tr><th>Model</th><th>Version</th><th>N</th><th>MAE</th><th>RMSE</th><th>Bias</th><th>Skill</th></tr></thead><tbody>"""+ "".join(rows)+"</tbody></table></div></html>"

if __name__=="__main__":
    print(render(json.load(sys.stdin)))
