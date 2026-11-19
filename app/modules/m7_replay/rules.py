from app.errors import DomainError
from datetime import timedelta
from decimal import Decimal as D
def audit(rows,bad,total,late_minutes):
    if len(rows)+len(bad)!=total:raise DomainError('INCOMPLETE','渠道行数不守恒')
    watermark=None;late=[]
    for row in sorted(rows,key=lambda r:r['_line']):
        if watermark and row['time']<watermark-timedelta(minutes=float(late_minutes)):
            late.append({'id':row['id'],'seat':row['seat'],'order':row['order'],'time':row['time'],'late_minutes':D(str((watermark-row['time']).total_seconds()))/60,'state':'已回放'})
        watermark=max(watermark,row['time']) if watermark else row['time']
    return {'input':total,'retained':len(rows),'isolated':len(bad),'late':late,'watermark':watermark}
