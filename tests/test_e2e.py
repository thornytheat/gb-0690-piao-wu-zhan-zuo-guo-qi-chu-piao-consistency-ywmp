from app.pipeline import run
from app.config import SAMPLES
def test_dirty_flow_reconciles(raw,isolate):
    result=run(raw)
    assert len(result["stages"])==7
    assert result["input_count"]==len(result["records"])+len(result["quarantine"])
def test_same_content_is_idempotent(raw,isolate):
    a=run(raw);b=run(raw)
    assert a["manifest"]["run_id"]==b["manifest"]["run_id"]
    assert a["manifest"]["created"]==b["manifest"]["created"]
def test_real_http_modules(client):
    for stage in range(1,8):
        reply=client.get(f"/api/m{stage}")
        assert reply.status_code==200
        assert len(reply.json["stages"])==stage
def test_invalid_csv_is_recoverable(client):
    result=client.post("/api/runs",json={"text":"bad,header\n1,2"})
    assert result.status_code==422
    assert result.json["code"]=="HEADER"
def test_real_pages_and_export(client):
    for stage in range(1,8): assert client.get(f"/m/{stage}").status_code==200
    response=client.get("/api/evidence.csv")
    assert response.status_code==200 and "原因码" in response.text
def test_stale_review_rejected(client):
    r=client.post("/api/runs",json={}).json
    body={"version":r["version"],"decision":"通过"}
    assert client.post("/api/review/"+r["manifest"]["run_id"],json=body).status_code==200
    assert client.post("/api/review/"+r["manifest"]["run_id"],json=body).status_code==409
