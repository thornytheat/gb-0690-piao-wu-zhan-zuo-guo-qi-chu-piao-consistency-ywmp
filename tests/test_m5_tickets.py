import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m5_tickets.rules import verify_tickets
def pay():return dict(channel='官方',seat='A-01',order='O',time=instant('2026-11-17T10:00:00Z'),amount=D(100),lease='L')
def issue(**kw):
 x=dict(id='I',channel='官方',seat='A-01',order='O',time=instant('2026-11-17T10:01:00Z'),type='issue',amount=D(100),ticket='000001',_line=2);x.update(kw);return x

def test_valid_ticket():
    assert verify_tickets([issue()],[pay()])[2][0]['ticket']=='000001'

def test_no_payment():
    assert verify_tickets([issue()],[])[1][0]['code']=='ORPHAN'

def test_amount_mismatch():
    assert verify_tickets([issue(amount=D(99))],[pay()])[1][0]['code']=='CONFLICT'

def test_double_issue():
    x,b,t=verify_tickets([issue(),issue(id='J',ticket='2')],[pay()]);assert len(t)==1 and b[0]['code']=='CONFLICT'

def test_real_ticket_count(raw):
    assert len(run(raw,stop=5,persist=False)['tickets'])==12

def test_real_unique_seats(raw):
    x=run(raw,stop=5,persist=False)['tickets'];assert len({r['seat'] for r in x})==len(x)

def test_real_money(raw):
    assert sum(D(x['amount']) for x in run(raw,stop=5,persist=False)['tickets'])==1200


def test_issue_channel_must_match_payment():
    good,bad,tickets=verify_tickets([issue(channel='团购')],[pay()])
    assert tickets==[] and bad[0]['code']=='CONFLICT'
