from app.reasons import rejected
from collections import defaultdict
def match_payments(rows,leases):
    good=[];bad=[];payments=[];paid=set()
    for row in sorted(rows,key=lambda x:(x['time'],x['id'])):
        if row['type']!='pay':good.append(row);continue
        candidates=[l for l in leases if l['seat']==row['seat'] and l['order']==row['order'] and l['start']<=row['time']<l['end']]
        if len(candidates)!=1:bad.append(rejected(row,'EXPIRED','付款未落入有效占座区间'));continue
        lease=candidates[0]
        if row['channel']!=lease['channel']:bad.append(rejected(row,'CONFLICT','支付渠道与占座渠道不符'));continue
        if lease['lease'] in paid:bad.append(rejected(row,'DUPLICATE','租约已支付'));continue
        paid.add(lease['lease']);payments.append({**row,'lease':lease['lease'],'state':'已支付'});good.append(row)
    return good,bad,payments
