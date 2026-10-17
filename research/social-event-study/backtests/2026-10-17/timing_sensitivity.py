"""Post-hoc sample diagnostics. Does not estimate usable alpha."""
from pathlib import Path
import json
import csv
from statistics import mean

BASE=Path(__file__).resolve().parent

def readcsv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def summarize(groups,prices):
    meta=[r for r in groups if r['layer']=='meta' and int(r['net_direction']) != 0]
    def vals(h):
        return [(r,float(r[f'return_{h}d_pct'])*int(r['net_direction'])) for r in meta if r[f'return_{h}d_pct']]
    thresholds={}
    for h in (1,3,5):
        v=vals(h)
        thresholds[str(h)]={'n':len(v),'sign_agreement':sum(x>0 for _,x in v),
            'favorable_at_least_1pct':sum(x>=1 for _,x in v),
            'favorable_at_least_2pct':sum(x>=2 for _,x in v)}
    today_to_next=[]
    for r in meta:
        if r['post_date_et'] in prices and r['anchor_date'] in prices:
            v=(prices[r['anchor_date']]/prices[r['post_date_et']]-1)*100
            today_to_next.append({'date':r['post_date_et'], 'return_pct':round(v,3),
                                   'sign':int(r['net_direction']), 'sign_agree':int(v*int(r['net_direction'])>0)})
    high_conf=[r for r in meta if r['post_date_et'] in ('2026-07-30','2026-10-02')]
    return {'status':'RETROSPECTIVE_SELECTION_SENSITIVITY_ONLY',
            'meta_loose_sample':len(meta), 'time_delay_anchor':thresholds,
            'counterfactual_assume_available_same_day_close':{
                'n':len(today_to_next),'sign_agreements':sum(r['sign_agree'] for r in today_to_next),
                'rows':today_to_next,
                'warning':'UNVERIFIED availability - not a trade or historical feasible signal'},
            'only_explicit_forward_interpretations':{
                'n':len(high_conf),
                'ids':['META-005','META-006'],
                '1d_at_least_1pct':sum(float(r['return_1d_pct'])*int(r['net_direction'])>=1 for r in high_conf)},
            'interpretation':'Strong sensitivity to thresholds and inferred intent; inferential validity = NONE'}

if __name__=='__main__':
    p={r['date']:float(r['close']) for r in readcsv(BASE.parent/'quantrade_social_event_lab'/'soxl_daily_2026_selected.csv')} if (BASE.parent/'quantrade_social_event_lab').exists() else {r['date']:float(r['close']) for r in readcsv(BASE.parents[1]/'2026-10-17'/'soxl_daily_2026_selected.csv')}
    x=summarize(readcsv(BASE/'thread_day_outcomes.csv'),p)
    (BASE/'timing_sensitivity.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(x,ensure_ascii=False,indent=2))