from .rules import receive
def execute(ctx):
    ctx.update(receive(ctx['source']));ctx['stages'].append({'title':'渠道接收','rows':ctx['records'],'metrics':{'输入':ctx['input_count'],'采信':len(ctx['records']),'隔离':len(ctx['quarantine'])}});return ctx
