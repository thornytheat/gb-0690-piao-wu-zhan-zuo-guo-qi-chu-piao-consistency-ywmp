from .rules import normalize,dedup
from app.normalize import instant,number
from app.errors import DomainError
from app.reasons import rejected
def execute(ctx):
    end=instant(ctx['params']['observation_end']);late=number(ctx['params']['late_minutes'])
    if late<0:raise DomainError('RANGE','迟到阈值不可为负')
    good=[]
    for row in ctx['records']:
        try:good.append(normalize(row,end))
        except DomainError as exc:ctx['quarantine'].append(rejected(row,exc.code,exc.message))
    good,bad=dedup(good);ctx['quarantine'].extend(bad);ctx['records']=good;ctx['observation_end']=end
    ctx['stages'].append({'title':'座席映射','rows':good,'metrics':{'席位目录':16,'事件':len(good),'渠道':len({r['channel'] for r in good})}});return ctx
