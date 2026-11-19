from app.reasons import rejected
# Lease replay owns only holds/releases; payment and issue events are judged by later modules.
def replay(rows,end):
    active={};leases=[];bad=[];retained=[]
    priority={'release':0,'hold':1,'pay':2,'issue':3}
    for row in sorted(rows,key=lambda x:(x['time'],priority[x['type']],x['id'])):
        seat=row['seat'];current=active.get(seat)
        if current is not None and current['end']<=row['time']:active.pop(seat);current=None
        if row['type']=='hold':
            if current is not None:bad.append(rejected(row,'OVERLAP','座席仍被其他租约占用'));continue
            lease={'lease':row['id'],'seat':seat,'order':row['order'],'channel':row['channel'],'start':row['time'],'end':row['expires'],'expires':row['expires'],'released':False,'source_line':row['_line']}
            leases.append(lease);active[seat]=lease
        elif row['type']=='release':
            if current is None or current['order']!=row['order']:bad.append(rejected(row,'STATE','释放事件没有对应占座'));continue
            current['end']=row['time'];current['released']=True;active.pop(seat)
        retained.append(row)
    for lease in leases:
        lease['state']='已释放' if lease['released'] else '已过期' if lease['end']<=end else '占用中'
    return retained,bad,leases
