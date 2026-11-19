import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m7_replay.rules import audit
def e(time,line):return dict(id=str(line),seat='A-01',order='O',time=instant('2026-11-17T'+time+':00Z'),_line=line)

def test_late_kept():
    # TRAP-13
    x=audit([e('10:00',2),e('09:00',3)],[],2,10);assert x['late'][0]['late_minutes']==60 and x['retained']==2

def test_watermark_monotonic():
    assert audit([e('10:00',2),e('09:00',3)],[],2,10)['watermark']==instant('2026-11-17T10:00:00Z')

def test_row_mismatch():
    with pytest.raises(DomainError):audit([],[],1,10)

def test_stale_review(client):
    # TRAP-26
    x=client.post('/api/runs',json={}).json;url='/api/review/'+x['manifest']['run_id'];payload={'version':1,'decision':'通过'}
    assert client.post(url,json=payload).status_code==200
    assert client.post(url,json=payload).status_code==409

def test_real_late(raw):
    assert len(run(raw,persist=False)['audit']['late'])>0

def test_real_count(raw):
    x=run(raw,persist=False);assert x['audit']['input']==x['audit']['retained']+x['audit']['isolated']

def test_real_idempotent(raw,isolate):
    assert run(raw)['manifest']['run_id']==run(raw)['manifest']['run_id']

