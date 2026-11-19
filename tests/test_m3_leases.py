import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m3_leases.rules import replay
def event(id,t,kind='hold',order='O',expires='10:15'):
 return dict(id=id,time=instant('2026-11-17T'+t+':00+08:00'),type=kind,seat='A-01',order=order,expires=instant('2026-11-17T'+expires+':00+08:00') if kind=='hold' else None,channel='官方',_line=int(id)+1)
END=instant('2026-11-18T00:00:00+08:00')

def test_expiration_endpoint_reusable():
    # TRAP-23
    x,b,l=replay([event('1','10:00'),event('2','10:15',order='P',expires='10:30')],END);assert len(l)==2 and b==[]

def test_overlap_rejected():
    x,b,l=replay([event('1','10:00'),event('2','10:10',order='P')],END);assert len(l)==1 and b[0]['code']=='OVERLAP'

def test_release_closes():
    x,b,l=replay([event('1','10:00'),event('2','10:05','release')],END);assert l[0]['end']==instant('2026-11-17T10:05:00+08:00') and l[0]['released']

def test_wrong_order_release():
    x,b,l=replay([event('1','10:00'),event('2','10:05','release','P')],END);assert b[0]['code']=='STATE'

def test_real_leases(raw):
    assert len(run(raw,stop=3,persist=False)['leases'])>=14

def test_real_expired(raw):
    assert all(x['state']=='已过期' for x in run(raw,stop=3,persist=False)['leases'])

def test_real_order_independent(raw):
    x=run(raw,stop=3,persist=False);assert len(x['records'])+len(x['quarantine'])==49

