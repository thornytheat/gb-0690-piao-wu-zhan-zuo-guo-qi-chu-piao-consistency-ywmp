import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m6_reconcile.rules import reconcile
def row(amount='100'):return dict(channel='官方',amount=D(amount))

def test_balanced():
    assert reconcile([row()],[row()])[0]['state']=='通过'

def test_pending_ticket():
    assert reconcile([row()],[])[0]['delta']==100

def test_count_mismatch():
    assert reconcile([row('0')],[])[0]['state']=='待出票'

def test_empty():
    assert reconcile([],[])==[]

def test_real_channel_count(raw):
    assert len(run(raw,stop=6,persist=False)['channel_balances'])==3

def test_real_pending(raw):
    x=run(raw,stop=6,persist=False)['channel_balances'];assert sum(D(r['delta']) for r in x)==200

def test_real_reconcile(raw):
    x=run(raw,stop=6,persist=False);assert len(x['payments'])-len(x['tickets'])==2

