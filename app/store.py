import os,sqlite3,json
from pathlib import Path
from app.errors import DomainError
def connection():
    path=Path(os.environ.get("DATA_DIR","data"));path.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path/"runs.sqlite",timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,review TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS settlements (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL DEFAULT '')")
    return db
def save(result):
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES(?,?)",(result["manifest"]["run_id"],json.dumps(result,ensure_ascii=False)))
    return fetch(result["manifest"]["run_id"])
def fetch(run_id):
    with connection() as db: row=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
    result=json.loads(row["payload"]);result["version"]=row["version"];result["review"]=row["review"]
    return result
def history():
    with connection() as db: rows=db.execute("SELECT id,version,review FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
    return [dict(row) for row in rows]
def review(run_id,version,decision):
    if decision not in ("通过","退回"): raise DomainError("REVIEW","请选择通过或退回")
    if not isinstance(version,int): raise DomainError("STALE","版本必须为整数")
    with connection() as db:
        cur=db.execute("UPDATE runs SET review=?,version=version+1 WHERE id=? AND version=?",(decision,run_id,version))
        if cur.rowcount!=1: raise DomainError("STALE","复核版本已更新",409)
    return fetch(run_id)
def save_settlement(doc):
    # INSERT OR IGNORE：同一结算重跑复用同一结算ID，绝不产生第二次额度扣减。
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO settlements(id,run_id,payload,created) VALUES(?,?,?,?)",
                   (doc["settlement_id"],doc["run_id"],json.dumps(doc,ensure_ascii=False),doc.get("created","")))
    return fetch_settlement(doc["settlement_id"])
def fetch_settlement(settlement_id):
    with connection() as db: row=db.execute("SELECT * FROM settlements WHERE id=?",(settlement_id,)).fetchone()
    if row is None: raise DomainError("NOT_FOUND","结算不存在",404)
    return json.loads(row["payload"])
def find_settlement(run_id,settlement_id=None):
    sql="SELECT payload FROM settlements WHERE run_id=?";args=[run_id]
    if settlement_id:sql+=" AND id=?";args.append(settlement_id)
    sql+=" ORDER BY rowid DESC LIMIT 1"
    with connection() as db: row=db.execute(sql,args).fetchone()
    return json.loads(row["payload"]) if row else None
def save_receipt(settlement_id,doc):
    # 回执裁决随结算快照整体覆盖保存；首次受理已通过唯一结算ID去重，重跑不会重复扣减。
    from app.normalize import serial
    with connection() as db:
        cur=db.execute("UPDATE settlements SET payload=? WHERE id=?",(json.dumps(serial(doc),ensure_ascii=False),settlement_id))
        if cur.rowcount!=1: raise DomainError("NOT_FOUND","结算不存在",404)
    return fetch_settlement(settlement_id)
