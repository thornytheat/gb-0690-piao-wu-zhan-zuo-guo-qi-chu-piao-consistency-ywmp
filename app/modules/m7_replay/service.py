from .rules import audit
from app.normalize import number
def execute(ctx):
    ctx['audit']=audit(ctx['records'],ctx['quarantine'],ctx['input_count'],number(ctx['params']['late_minutes']))
    ctx['stages'].append({'title':'补传复核','rows':ctx['audit']['late'],'metrics':{'补传事件':len(ctx['audit']['late']),'采信':len(ctx['records']),'隔离':len(ctx['quarantine'])}});return ctx
