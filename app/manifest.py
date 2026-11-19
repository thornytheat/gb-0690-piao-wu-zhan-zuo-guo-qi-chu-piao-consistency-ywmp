import hashlib, json
from datetime import datetime, timezone
from app.config import RULE_VERSION
def make(raw,params):
    digest=hashlib.sha256(raw).hexdigest()
    key=hashlib.sha256((digest+json.dumps(params,sort_keys=True,ensure_ascii=False)+RULE_VERSION).encode()).hexdigest()
    return {"run_id":key[:20],"sha256":digest,"rules":RULE_VERSION,"params":params,
            "created":datetime.now(timezone.utc).isoformat(),"bytes":len(raw)}
