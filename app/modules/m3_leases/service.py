from .rules import replay
def execute(ctx):
    rows,bad,leases=replay(ctx['records'],ctx['observation_end']);ctx['records']=rows;ctx['quarantine'].extend(bad);ctx['leases']=leases
    ctx['stages'].append({'title':'占座租约','rows':leases,'metrics':{'有效租约':len(leases),'占座冲突':sum(x['code']=='OVERLAP' for x in bad),'已释放':sum(x['released'] for x in leases)}});return ctx
