import csv,io,json
from flask import Flask,request,jsonify,redirect,Response
from importlib import import_module
from app.config import STAGES,MAX_BYTES
from app.errors import DomainError
from app.normalize import serial
from app.pipeline import run
from app import store
from app.web import view
def create_app():
    app=Flask(__name__);app.config["MAX_CONTENT_LENGTH"]=MAX_BYTES
    app.json.ensure_ascii=False
    @app.errorhandler(DomainError)
    def domain_error(error): return jsonify(code=error.code,message=error.message),error.status
    @app.errorhandler(413)
    def large(error): return jsonify(code="TOO_LARGE",message="文件超过4MB"),413
    @app.get("/health")
    def health(): return {"status":"ok"}
    @app.get("/")
    def home(): return redirect("/m/1")
    @app.get("/m/<int:stage>")
    def page(stage): return view(stage)
    @app.post("/api/runs")
    def start():
        if request.files:
            file=request.files.get("file")
            if file is None: raise DomainError("FILE","请选择文件")
            raw=file.read(MAX_BYTES+1)
            try: params=json.loads(request.form.get("params","{}"))
            except ValueError: raise DomainError("PARAMS","参数格式错误")
        else:
            payload=request.get_json(silent=True)
            if not isinstance(payload,dict): raise DomainError("BODY","请求必须是对象")
            raw=payload.get("text")
            if raw is not None and not isinstance(raw,str): raise DomainError("TEXT","数据必须为文本")
            params=payload.get("params")
        return jsonify(run(raw,params))
    @app.get("/api/runs/<run_id>")
    def get_run(run_id): return jsonify(store.fetch(run_id))
    @app.get("/api/history")
    def history(): return jsonify(store.history())
    @app.post("/api/review/<run_id>")
    def review(run_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict): raise DomainError("BODY","请求必须是对象")
        return jsonify(store.review(run_id,data.get("version"),data.get("decision")))
    @app.get("/api/evidence.csv")
    def evidence():
        result=store.fetch(request.args["run"]) if request.args.get("run") else run()
        stream=io.StringIO(newline="");writer=csv.writer(stream)
        writer.writerow(["批次","行号","主键","原因码","证据"])
        for row in result.get("records",[]):
            writer.writerow([result["manifest"]["run_id"],row.get("_line",""),row.get("id",row.get("event_id","")),"PASS",json.dumps(serial(row),ensure_ascii=False)])
        for row in result["quarantine"]:
            writer.writerow([result["manifest"]["run_id"],row["line"],row["key"],row["code"],json.dumps(row,ensure_ascii=False)])
        return Response("\ufeff"+stream.getvalue(),content_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=evidence.csv"})
    for n,name in enumerate(STAGES,1): app.register_blueprint(import_module(f"app.modules.m{n}_{name}.handler").bp)
    return app
app=create_app()
