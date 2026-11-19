from .rules import reconcile
def execute(ctx):
    ctx['channel_balances']=reconcile(ctx['payments'],ctx['tickets'])
    ctx['stages'].append({'title':'渠道对账','rows':ctx['channel_balances'],'metrics':{'渠道':len(ctx['channel_balances']),'有效支付':len(ctx['payments']),'悬单':len(ctx['payments'])-len(ctx['tickets'])}});return ctx
