import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.modules.m1_receive.rules import receive
from app.config import SAMPLES

def test_bom(raw):
    # TRAP-02
    assert receive(raw)['records'][0]['id']=='00001'

def test_real_count(raw):
    assert receive(raw)['input_count']==49

def test_real_width(raw):
    assert receive(raw)['quarantine'][0]['code']=='COLUMN_COUNT'

def test_large_id(raw):
    # TRAP-09
    assert any(x['id']=='9007199254740993123' for x in receive(raw)['records'])

def test_empty():
    with pytest.raises(DomainError):receive(b'')

def test_header():
    with pytest.raises(DomainError):receive(b'a,b\n1,2')

def test_legacy():
    assert receive((SAMPLES/'legacy.csv').read_bytes())['encoding']=='gb18030'

