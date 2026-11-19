from .rules import verify_tickets
def execute(ctx):
    rows,bad,tickets=verify_tickets(ctx['records'],ctx['payments']);ctx['records']=rows;ctx['quarantine'].extend(bad);ctx['tickets']=tickets
    ctx['stages'].append({'title':'出票核验','rows':tickets,'metrics':{'已出票':len(tickets),'售出席位':len({x['seat'] for x in tickets}),'拒绝出票':len(bad)}});return ctx
