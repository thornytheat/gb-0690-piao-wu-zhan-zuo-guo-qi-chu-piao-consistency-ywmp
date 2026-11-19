from .rules import match_payments
def execute(ctx):
    rows,bad,payments=match_payments(ctx['records'],ctx['leases']);ctx['records']=rows;ctx['quarantine'].extend(bad);ctx['payments']=payments
    ctx['stages'].append({'title':'支付归属','rows':payments,'metrics':{'有效支付':len(payments),'无效支付':len(bad),'金额 CNY':str(sum((r['amount'] for r in payments),0))}});return ctx
