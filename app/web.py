from flask import render_template,request
from app import store
from app.pipeline import run
from app.config import TITLE,MODULES,STAGES,COLUMNS,SAMPLES,DEFAULTS
def view(stage):
    if not 1<=stage<=8: return "页面不存在",404
    run_id=request.args.get("run")
    if run_id:
        result=store.fetch(run_id)
        if stage==8 and len(result["stages"])<8:
            # 旧批次只跑到 M7：按相同输入与参数补算结算阶段，复用同一批次不产生重复扣减。
            result=run(None,result["manifest"]["params"],stop=8,persist=False)
    else:
        result=run(None,None,stop=8) if stage==8 else run()
    sample=(SAMPLES/"dirty.csv").read_text(encoding="utf-8-sig")
    data=result["stages"][stage-1]
    sold={t['seat'] for t in result['tickets']};paid={t['seat'] for t in result['payments']};held={t['seat'] for t in result['leases']}
    seats=[{'seat':f'A-{i:02d}','state':'已出票' if f'A-{i:02d}' in sold else '待出票' if f'A-{i:02d}' in paid else '已过期' if f'A-{i:02d}' in held else '空闲'} for i in range(1,17)]
    settlement=store.find_settlement(result["manifest"]["run_id"]) if stage==8 else None
    return render_template(f"m{stage}.html",title=TITLE,modules=MODULES,stage=stage,result=result,data=data,
                           sample=sample,defaults=DEFAULTS,columns=COLUMNS,history=store.history(),seats=seats,
                           settlement=settlement)
