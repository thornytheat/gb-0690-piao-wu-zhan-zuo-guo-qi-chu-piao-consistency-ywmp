import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.errors import DomainError
from app.normalize import instant
from app.config import SAMPLES, QUOTA
from app import store
from app.modules.m8_settlement.rules import adjudicate, submit_receipt, SOLD, PAID_PENDING, AWAIT, RETURNED

DEADLINE = '2026-11-17T10:42:00+08:00'
HEADER = 'id,channel,seat,order,time,type,expires,version,amount,ticket\n'


def hold(eid, channel, seat, order, t='10:00', expires='10:30'):
    return f'{eid},{channel},{seat},{order},2026-11-17T{t}:00+08:00,hold,2026-11-17T{expires}:00+08:00,1,0,\n'


def pay(eid, channel, seat, order, t, amount='100'):
    return f'{eid},{channel},{seat},{order},2026-11-17T{t}:00+08:00,pay,,1,{amount},\n'


def issue(eid, channel, seat, order, t, ticket, amount='100'):
    return f'{eid},{channel},{seat},{order},2026-11-17T{t}:00+08:00,issue,,1,{amount},{ticket}\n'


def settlement(raw, params=None):
    out = run(raw, {'settle_deadline': DEADLINE, **(params or {})}, stop=8, persist=False)
    return out['settlement'], out


def seat_state(doc, seat):
    return next(x for x in doc['seat_ledger'] if x['seat'] == seat)['state']


def test_quota_covers_all_16_seats_once():
    seats = [s for group in QUOTA.values() for s in group]
    assert len(seats) == 16 and len(set(seats)) == 16


def test_sold_seat_keeps_old_quota():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30') + pay('P1', '官方', 'A-01', 'O1', '10:05') \
        + issue('I1', '官方', 'A-01', 'O1', '10:06', 'T1')
    doc, _ = settlement(raw)
    assert seat_state(doc, 'A-01') == SOLD
    ch = next(c for c in doc['channels'] if c['channel'] == '官方')
    assert ch['occupied'] == 1 and ch['quota_left'] == ch['quota'] - 1


def test_paid_pending_ticket_keeps_old_quota():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30') + pay('P1', '官方', 'A-01', 'O1', '10:05')
    doc, _ = settlement(raw)
    assert seat_state(doc, 'A-01') == PAID_PENDING


def test_open_hold_at_deadline_awaits_receipt():
    raw = HEADER + hold('H1', '票社', 'A-02', 'O2', expires='11:30')
    doc, _ = settlement(raw)
    assert seat_state(doc, 'A-02') == AWAIT
    assert doc['totals']['pending'] >= 1


def test_unsold_seat_returns_to_pool():
    raw = HEADER + hold('H1', '团购', 'A-03', 'O3', expires='10:10')
    doc, _ = settlement(raw)
    assert seat_state(doc, 'A-03') == RETURNED
    assert doc['totals']['returned'] >= 1


def test_seat_conservation():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='10:10')
    doc, _ = settlement(raw)
    t = doc['totals']
    assert t['occupied'] + t['pending'] + t['returned'] == t['quota'] == 16


def test_late_receipt_after_expiry_rejected_in_adjudication():
    # 占座 10:10 到期，支付回执 10:50 才到（晚于 10:42 截止且租约已失效），必须拒绝。
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='10:10') \
        + pay('LATE1', '官方', 'A-01', 'O1', '10:50')
    doc, _ = settlement(raw)
    assert seat_state(doc, 'A-01') == RETURNED
    assert any(r['id'] == 'LATE1' and r['code'] == 'LATE_REJECT' and not r['accepted']
               for r in doc['receipts'])


def test_late_receipt_inside_valid_lease_is_accepted():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30')
    doc, out = settlement(raw)
    assert seat_state(doc, 'A-01') == AWAIT
    receipt = {'id': 'P9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
               'time': instant('2026-11-17T10:50:00+08:00'), 'type': 'pay',
               'amount': D('100'), 'ticket': ''}
    decision = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], receipt)
    assert decision['accepted'] and decision['code'] == 'PASS'
    assert seat_state(doc, 'A-01') == PAID_PENDING


def test_receipt_on_returned_seat_rejected():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='10:10')
    doc, out = settlement(raw)
    receipt = {'id': 'P9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
               'time': instant('2026-11-17T10:50:00+08:00'), 'type': 'pay',
               'amount': D('100'), 'ticket': ''}
    decision = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], receipt)
    assert not decision['accepted'] and decision['code'] == 'LATE_REJECT'
    assert seat_state(doc, 'A-01') == RETURNED


def test_replay_same_receipt_does_not_deduct_twice():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30')
    doc, out = settlement(raw)
    receipt = {'id': 'P9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
               'time': instant('2026-11-17T10:50:00+08:00'), 'type': 'pay',
               'amount': D('100'), 'ticket': ''}
    first = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], dict(receipt))
    occupied_after_first = doc['totals']['occupied']
    second = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], dict(receipt))
    assert first['accepted'] and second.get('replayed') and second['code'] == 'PASS'
    assert doc['totals']['occupied'] == occupied_after_first
    assert sum(1 for r in doc['receipts'] if r['id'] == 'P9') == 1


def test_second_payment_on_same_seat_rejected():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30') + pay('P1', '官方', 'A-01', 'O1', '10:05')
    doc, out = settlement(raw)
    receipt = {'id': 'P9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
               'time': instant('2026-11-17T10:50:00+08:00'), 'type': 'pay',
               'amount': D('100'), 'ticket': ''}
    decision = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], receipt)
    assert not decision['accepted'] and decision['code'] == 'DUPLICATE'


def test_cross_channel_receipt_rejected():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30')
    doc, out = settlement(raw)
    receipt = {'id': 'P9', 'channel': '团购', 'seat': 'A-01', 'order': 'O1',
               'time': instant('2026-11-17T10:50:00+08:00'), 'type': 'pay',
               'amount': D('100'), 'ticket': ''}
    decision = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], receipt)
    assert not decision['accepted'] and decision['code'] == 'CONFLICT'


def test_cross_quota_hold_returns_seat_and_records_breach():
    # 团购在官方额度座席 A-01 上成交：不得占用官方额度，座席回总池并留痕。
    raw = HEADER + hold('H1', '团购', 'A-01', 'O1') + pay('P1', '团购', 'A-01', 'O1', '10:05')
    doc, _ = settlement(raw)
    assert seat_state(doc, 'A-01') == RETURNED
    breach = [r for r in doc['receipts'] if r['seat'] == 'A-01']
    assert breach and breach[0]['code'] == 'OVERLAP' and breach[0]['held_by'] == '团购'
    assert next(c for c in doc['channels'] if c['channel'] == '官方')['occupied'] == 0


def test_pay_then_issue_closure_via_receipts():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30')
    doc, out = settlement(raw)
    pay_receipt = {'id': 'P9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
                   'time': instant('2026-11-17T10:50:00+08:00'), 'type': 'pay',
                   'amount': D('100'), 'ticket': ''}
    submit_receipt(doc, out['leases'], out['payments'], out['tickets'], pay_receipt)
    issue_receipt = {'id': 'I9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
                     'time': instant('2026-11-17T10:51:00+08:00'), 'type': 'issue',
                     'amount': D('100'), 'ticket': 'T9001'}
    decision = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], issue_receipt)
    assert decision['accepted'] and seat_state(doc, 'A-01') == SOLD


def test_issue_without_payment_is_orphan():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30')
    doc, out = settlement(raw)
    receipt = {'id': 'I9', 'channel': '官方', 'seat': 'A-01', 'order': 'O1',
               'time': instant('2026-11-17T10:51:00+08:00'), 'type': 'issue',
               'amount': D('100'), 'ticket': 'T9001'}
    decision = submit_receipt(doc, out['leases'], out['payments'], out['tickets'], receipt)
    assert not decision['accepted'] and decision['code'] == 'ORPHAN'


def test_deadline_after_observation_end_rejected():
    raw = (SAMPLES / 'dirty.csv').read_bytes()
    with pytest.raises(DomainError) as exc:
        run(raw, {'settle_deadline': '2026-11-19T00:00:00+08:00'}, stop=8, persist=False)
    assert exc.value.code == 'RANGE'


def test_missing_deadline_rejected():
    raw = HEADER + hold('H1', '官方', 'A-01', 'O1', expires='11:30')
    with pytest.raises(DomainError) as exc:
        run(raw, {'settle_deadline': ''}, stop=8, persist=False)
    assert exc.value.code == 'MISSING'


def test_real_sample_has_all_pending_work_states(raw):
    out = run(raw, {'settle_deadline': DEADLINE}, stop=8, persist=False)
    doc = out['settlement']
    states = {x['state'] for x in doc['seat_ledger']}
    # 脏样例在 10:42 截止点同时呈现四种裁决：成交占旧额度、已收款待出票、回执待处理、空座回总池
    assert {SOLD, PAID_PENDING, AWAIT, RETURNED} <= states
    assert any(r['code'] == 'LATE_REJECT' for r in doc['receipts'])
    assert doc['totals']['quota'] == 16
    assert doc['totals']['occupied'] + doc['totals']['pending'] + doc['totals']['returned'] == 16


def test_real_sample_idempotent_settlement_id(raw):
    a = run(raw, {'settle_deadline': DEADLINE}, stop=8, persist=False)['settlement']
    b = run(raw, {'settle_deadline': DEADLINE}, stop=8, persist=False)['settlement']
    assert a['settlement_id'] == b['settlement_id']


def test_deadline_change_produces_new_settlement(raw):
    a = run(raw, {'settle_deadline': DEADLINE}, stop=8, persist=False)['settlement']
    b = run(raw, {'settle_deadline': '2026-11-17T10:16:00+08:00'}, stop=8, persist=False)['settlement']
    assert a['settlement_id'] != b['settlement_id']


def test_api_rerun_inserts_single_settlement_row(client, raw):
    text = raw.decode('utf-8-sig')
    first = client.post('/api/m8', json={'text': text, 'params': {'settle_deadline': DEADLINE}}).get_json()
    second = client.post('/api/m8', json={'text': text, 'params': {'settle_deadline': DEADLINE}}).get_json()
    assert first['settlement']['settlement_id'] == second['settlement']['settlement_id']
    with store.connection() as db:
        count = db.execute('SELECT COUNT(*) FROM settlements').fetchone()[0]
    assert count == 1


def test_api_late_receipt_after_expiry_is_refused(client, raw):
    text = raw.decode('utf-8-sig')
    rid = client.post('/api/m8', json={'text': text, 'params': {'settle_deadline': DEADLINE}}).get_json()['run_id']
    resp = client.post('/api/m8/receipt', json={
        'run_id': rid, 'id': 'WEB-LATE', 'channel': '官方', 'seat': 'A-15', 'order': '09915',
        'time': '2026-11-17T10:50:00+08:00', 'type': 'pay', 'amount': '100'})
    assert resp.status_code == 422
    assert resp.get_json()['decision']['code'] == 'LATE_REJECT'


def test_api_valid_receipt_accepted_and_persisted(client, raw):
    text = raw.decode('utf-8-sig')
    rid = client.post('/api/m8', json={'text': text, 'params': {'settle_deadline': DEADLINE}}).get_json()['run_id']
    resp = client.post('/api/m8/receipt', json={
        'run_id': rid, 'id': 'WEB-OK', 'channel': '官方', 'seat': 'A-15', 'order': '09915',
        'time': '2026-11-17T10:14:30+08:00', 'type': 'pay', 'amount': '100'})
    assert resp.status_code == 200 and resp.get_json()['decision']['accepted']
    persisted = store.find_settlement(rid)
    assert any(r['id'] == 'WEB-OK' and r['accepted'] for r in persisted['receipts'])
    # 重放同一回执：幂等，不新增台账行
    again = client.post('/api/m8/receipt', json={
        'run_id': rid, 'id': 'WEB-OK', 'channel': '官方', 'seat': 'A-15', 'order': '09915',
        'time': '2026-11-17T10:14:30+08:00', 'type': 'pay', 'amount': '100'})
    assert again.status_code == 200 and again.get_json()['decision'].get('replayed')
    assert sum(1 for r in store.find_settlement(rid)['receipts'] if r['id'] == 'WEB-OK') == 1


def test_m8_page_runs_and_links(client, raw):
    text = raw.decode('utf-8-sig')
    rid = client.post('/api/runs', json={'text': text}).get_json()['manifest']['run_id']
    page = client.get(f'/m/8?run={rid}')
    assert page.status_code == 200 and '额度结算'.encode() in page.data
