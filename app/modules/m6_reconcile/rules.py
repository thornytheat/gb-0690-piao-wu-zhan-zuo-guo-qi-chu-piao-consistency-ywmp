from decimal import Decimal as D
from collections import defaultdict
def reconcile(payments,tickets):
    channels=defaultdict(lambda:{'paid':D(0),'ticketed':D(0),'payments':0,'tickets':0})
    for p in payments:channels[p['channel']]['paid']+=p['amount'];channels[p['channel']]['payments']+=1
    for t in tickets:channels[t['channel']]['ticketed']+=t['amount'];channels[t['channel']]['tickets']+=1
    result=[]
    for name,row in sorted(channels.items()):result.append({'channel':name,**row,'delta':row['paid']-row['ticketed'],'state':'通过' if row['paid']==row['ticketed'] and row['payments']==row['tickets'] else '待出票'})
    return result
