import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m2_seats.rules import normalize,dedup
END=instant('2026-11-18T00:00:00+08:00')
def row(**kw):
 x=dict(id='00001',channel='官方',seat='A01',order='00001',time='2026-11-17T10:00:00+08:00',type='hold',expires='2026-11-17T10:15:00+08:00',version='1',amount='100',ticket='',_line=2);x.update(kw);return x

def test_seat_alias():
    # TRAP-08
    assert normalize(row(),END)['seat']=='A-01' and normalize(row(),END)['order']=='00001'

def test_time_equivalence():
    # TRAP-11
    assert normalize(row(time='2026-11-17T02:00:00Z'),END)['time']==normalize(row(),END)['time']

def test_expired_lease():
    with pytest.raises(DomainError):normalize(row(expires='2026-11-17T10:00:00+08:00'),END)

def test_unknown_seat():
    with pytest.raises(DomainError):normalize(row(seat='B99'),END)

def test_real_conflict(raw):
    # TRAP-14
    assert sum(x['code']=='CONFLICT' for x in run(raw,stop=2,persist=False)['quarantine'])==2

def test_real_seats(raw):
    assert all(x['seat'].startswith('A-') for x in run(raw,stop=2,persist=False)['records'])

def test_real_channels(raw):
    assert len({x['channel'] for x in run(raw,stop=2,persist=False)['records']})==3

