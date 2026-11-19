import hashlib
from datetime import datetime, timezone
from app.normalize import instant, serial
from app.config import RULE_VERSION
from app.errors import DomainError
from .rules import adjudicate


def settlement_id(run_id, deadline):
    key = hashlib.sha256(f"{run_id}|{deadline.isoformat()}|{RULE_VERSION}".encode()).hexdigest()
    return "STL" + key[:17]


def deadline_of(ctx):
    value = ctx['params'].get('settle_deadline')
    if value in (None, ''):
        raise DomainError('MISSING', '缺少截止时刻 settle_deadline')
    try:
        deadline = instant(value)
    except DomainError:
        raise
    if deadline > ctx['observation_end']:
        raise DomainError('RANGE', '截止时刻不能晚于观测终点')
    return deadline


def build(ctx):
    deadline = deadline_of(ctx)
    doc = adjudicate(ctx['leases'], ctx['payments'], ctx['tickets'], ctx['quarantine'], deadline)
    doc['settlement_id'] = settlement_id(ctx['manifest']['run_id'], deadline)
    doc['run_id'] = ctx['manifest']['run_id']
    doc['rules'] = RULE_VERSION
    doc['created'] = datetime.now(timezone.utc).isoformat()
    return serial(doc)


def execute(ctx):
    doc = build(ctx)
    ctx['settlement'] = doc
    totals = doc['totals']
    ctx['stages'].append({'title': '额度结算', 'rows': doc['seat_ledger'],
                          'metrics': {'固定额度': totals['quota'], '仍占旧额度': totals['occupied'],
                                      '已回总池': totals['returned'], '回执待处理': totals['pending'],
                                      '拒绝回执': totals['late_rejects']}})
    return ctx
