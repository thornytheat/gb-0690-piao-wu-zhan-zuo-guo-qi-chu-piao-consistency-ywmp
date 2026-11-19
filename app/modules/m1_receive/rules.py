from app.normalize import rows_from
from app.reasons import rejected
def receive(raw):
    result=rows_from(raw,['id','channel','seat','order','time','type','expires','version','amount','ticket']);good=[]
    for row in result['raw']:
        if not row['id'] or not row['order']:result['quarantine'].append(rejected(row,'MISSING','事件或订单缺失'))
        else:good.append(row)
    result['records']=good;return result
