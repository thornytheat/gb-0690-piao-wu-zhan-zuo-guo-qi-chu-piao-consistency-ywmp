from flask import Blueprint,request,jsonify
from app.pipeline import run
from app.errors import DomainError
bp=Blueprint("m1",__name__)
@bp.route("/api/m1",methods=["GET","POST"])
def endpoint():
    payload=request.get_json(silent=True) if request.method=="POST" else {}
    if not isinstance(payload,dict): raise DomainError("BODY","请求必须是对象")
    raw=payload.get("text")
    if raw is not None and not isinstance(raw,str): raise DomainError("TEXT","数据必须为文本")
    return jsonify(run(raw,payload.get("params"),stop=1,persist=False))
