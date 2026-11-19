from app.normalize import number,instant
from app.errors import DomainError
from collections import defaultdict
from app.reasons import rejected
SEATS={f'A-{i:02d}':f'A-{i:02d}' for i in range(1,17)}
SEATS.update({f'A{i:02d}':f'A-{i:02d}' for i in range(1,17)})
def normalize(row,end):
    out=dict(row);seat=SEATS.get(row['seat'])
    if seat is None:raise DomainError('UNMAPPED','座席不在演出目录')
    if row['channel'] not in ('官方','票社','团购'):raise DomainError('UNMAPPED','渠道未登记')
    out['seat']=seat;out['time']=instant(row['time']);out['amount']=number(row['amount'])
    if out['time']>end or out['amount']<0:raise DomainError('RANGE','时刻或金额越界')
    v=number(row['version'])
    if v<1 or v!=v.to_integral():raise DomainError('RANGE','版本须为正整数')
    out['version']=int(v)
    if row['type'] not in ('hold','release','pay','issue'):raise DomainError('STATE','事件类型不支持')
    out['expires']=instant(row['expires']) if row['type']=='hold' else None
    if out['expires'] and out['expires']<=out['time']:raise DomainError('RANGE','租约到期早于占座')
    return out
def dedup(rows):
    groups=defaultdict(list)
    for row in rows:groups[row['id']].append(row)
    good=[];bad=[]
    for key,group in sorted(groups.items()):
        latest=max(x['version'] for x in group);top=[x for x in group if x['version']==latest]
        sig=lambda x:tuple(str(x[k]) for k in ['seat','order','time','type','expires','amount','ticket','channel'])
        if len({sig(x) for x in top})>1:bad.extend(rejected(x,'CONFLICT','同版渠道事件矛盾') for x in group);continue
        winner=min(top,key=lambda x:x['_line']);good.append(winner);bad.extend(rejected(x,'DUPLICATE','重复或旧版事件') for x in group if x is not winner)
    return good,bad
