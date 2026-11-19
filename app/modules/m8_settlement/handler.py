from flask import Blueprint, request, jsonify
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant, number
from app import store
from .rules import submit_receipt

bp = Blueprint("m8", __name__)


@bp.route("/api/m8", methods=["GET", "POST"])
def endpoint():
    payload = request.get_json(silent=True) if request.method == "POST" else {}
    if not isinstance(payload, dict):
        raise DomainError("BODY", "请求必须是对象")
    raw = payload.get("text")
    if raw is not None and not isinstance(raw, str):
        raise DomainError("TEXT", "数据必须为文本")
    # persist=False：结算快照由 settlements 表单独持久化，避免与 runs 快照互相覆盖。
    result = run(raw, payload.get("params"), stop=8, persist=False)
    store.save(result)
    # 同一输入与同一截止时刻产生同一结算ID；重跑命中已存在快照，不重复扣减。
    doc = store.find_settlement(result["manifest"]["run_id"], result["settlement"]["settlement_id"])
    if doc is None:
        doc = store.save_settlement(result["settlement"])
    return jsonify({"run_id": result["manifest"]["run_id"], "settlement": doc})


def _parse_receipt(payload):
    required = ("id", "channel", "seat", "order", "time", "type")
    missing = [name for name in required if not str(payload.get(name, "")).strip()]
    if missing:
        raise DomainError("MISSING", "回执缺少必填字段: " + ",".join(missing))
    if payload["type"] not in ("pay", "issue"):
        raise DomainError("STATE", "回执事件类型仅支持 pay 或 issue")
    receipt = {k: str(payload[k]).strip() for k in ("id", "channel", "seat", "order", "type")}
    receipt["time"] = instant(payload["time"])
    receipt["amount"] = number(payload.get("amount", "0"))
    receipt["ticket"] = str(payload.get("ticket", "")).strip()
    return receipt


def _hydrate(result):
    # SQLite 中的批次快照已把时间序列化为字符串，裁决前还原为带时区 datetime。
    for lease in result.get("leases", []):
        for key in ("start", "end", "expires"):
            if isinstance(lease.get(key), str):
                lease[key] = instant(lease[key])
    for group in ("payments", "tickets"):
        for row in result.get(group, []):
            if isinstance(row.get("time"), str):
                row["time"] = instant(row["time"])
    return result


@bp.route("/api/m8/receipt", methods=["POST"])
def receipt_endpoint():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise DomainError("BODY", "请求必须是对象")
    run_id = str(payload.get("run_id", "")).strip()
    if not run_id:
        raise DomainError("MISSING", "请指定结算所属批次 run_id")
    receipt = _parse_receipt(payload)
    result = _hydrate(store.fetch(run_id))
    settlement = store.find_settlement(run_id)
    if settlement is None:
        from app.pipeline import run as _run
        rebuilt = _run(None, result["manifest"]["params"], stop=8, persist=False)
        settlement = store.save_settlement(rebuilt["settlement"])
    decision = submit_receipt(settlement, result["leases"], result["payments"], result["tickets"], receipt)
    doc = store.save_receipt(settlement["settlement_id"], settlement)
    status = 200 if decision["accepted"] else 422
    return jsonify({"decision": decision, "settlement": doc}), status
