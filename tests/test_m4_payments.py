import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m4_payments.rules import match_payments
def l(end='10:15'):return dict(lease='L',channel='官方',seat='A-01',order='O',start=instant('2026-11-17T10:00:00Z'),end=instant('2026-11-17T'+end+':00Z'))
def p(t='10:10',id='1'):return dict(id=id,channel='官方',seat='A-01',order='O',time=instant('2026-11-17T'+t+':00Z'),type='pay',amount=D(100),_line=2)

def test_before_expiry_paid():
    assert match_payments([p()],[l()])[2][0]['lease']=='L'

def test_at_expiry_rejected():
    x,b,pay=match_payments([p('10:15')],[l()]);assert pay==[] and b[0]['code']=='EXPIRED'

def test_released_payment_cannot_revive():
    x,b,pay=match_payments([p('10:10')],[l('10:05')]);assert pay==[] and b[0]['code']=='EXPIRED'

def test_duplicate_payment():
    x,b,pay=match_payments([p(),p(id='2')],[l()]);assert len(pay)==1 and b[0]['code']=='DUPLICATE'

def test_real_payments(raw):
    assert len(run(raw,stop=4,persist=False)['payments'])==14

def test_real_expiry_evidence(raw):
    assert sum(x['code']=='EXPIRED' for x in run(raw,stop=4,persist=False)['quarantine'])>=1

def test_real_money(raw):
    assert sum(D(x['amount']) for x in run(raw,stop=4,persist=False)['payments'])==1400


def test_payment_channel_must_match_lease():
    item=p();item['channel']='团购'
    good,bad,payments=match_payments([item],[l()])
    assert payments==[] and bad[0]['code']=='CONFLICT'
