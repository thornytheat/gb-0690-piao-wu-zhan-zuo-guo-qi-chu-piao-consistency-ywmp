from decimal import Decimal as D
from datetime import datetime
from app.normalize import instant
from app.errors import DomainError
from app.reasons import REASONS
from app.config import QUOTA

# 截止结算逐席裁决：成交仍占旧额度，空座回总池，截止时占座仍有效的悬单留作回执待处理。
SOLD = '成交已出票'
PAID_PENDING = '成交待出票'
AWAIT = '回执待处理'
RETURNED = '已回总池'
OCCUPYING = (SOLD, PAID_PENDING)


def _dt(value):
    return value if isinstance(value, datetime) else instant(value)


def _active_lease(leases, seat, moment):
    moment = _dt(moment)
    hits = [l for l in leases if l['seat'] == seat and _dt(l['start']) <= moment < _dt(l['end'])]
    return hits[0] if len(hits) == 1 else None


def summarize(seat_ledger):
    channels = []
    for channel, seats in QUOTA.items():
        rows = [x for x in seat_ledger if x['channel'] == channel]
        occupied = sum(x['state'] in OCCUPYING for x in rows)
        pending = sum(x['state'] == AWAIT for x in rows)
        returned = sum(x['state'] == RETURNED for x in rows)
        channels.append({'channel': channel, 'quota': len(seats), 'occupied': occupied,
                         'pending': pending, 'returned': returned, 'quota_left': len(seats) - occupied,
                         'state': '额度已满' if occupied == len(seats) else '有空座已回池' if returned else '待回执'})
    return channels


def adjudicate(leases, payments, tickets, quarantine, deadline):
    # M1-M7 按事件时间完整回放；截止结算只采信截止点之前到达的成交回执。
    payments = [p for p in payments if _dt(p['time']) < deadline]
    tickets = [t for t in tickets if _dt(t['time']) < deadline]
    pay_by_seat, ticket_by_seat = {}, {}
    for p in payments:
        pay_by_seat.setdefault(p['seat'], []).append(p)
    for t in tickets:
        ticket_by_seat[t['seat']] = t

    seat_ledger = []
    quota_breaches = []
    for channel, seats in QUOTA.items():
        for seat in seats:
            seat_pays = [p for p in pay_by_seat.get(seat, []) if p['channel'] == channel]
            foreign_pays = [p for p in pay_by_seat.get(seat, []) if p['channel'] != channel]
            ticket = ticket_by_seat.get(seat) if seat in ticket_by_seat and ticket_by_seat[seat]['channel'] == channel else None
            lease = _active_lease(leases, seat, deadline)
            lease_foreign = lease is not None and lease['channel'] != channel
            # 渠道只能在开售前分到的固定额度内成交：他渠道在本额度座席上的占座/成交不计本渠道，座席按空座回池。
            if lease_foreign or foreign_pays or (seat in ticket_by_seat and ticket is None):
                foreign = lease if lease_foreign else ((foreign_pays[0] if foreign_pays else ticket_by_seat[seat]))
                quota_breaches.append({'seat': seat, 'channel': channel, 'lease': foreign.get('lease', ''),
                                       'order': foreign.get('order', ''), 'held_by': foreign['channel'],
                                       'time': foreign.get('time'), 'type': foreign.get('type', 'hold'),
                                       'amount': str(foreign.get('amount', '')), 'ticket': foreign.get('ticket', ''),
                                       'id': foreign.get('id', foreign.get('lease', '')), 'accepted': False,
                                       'code': 'OVERLAP', 'reason': REASONS['OVERLAP'],
                                       'detail': f"{foreign['channel']}成交超出本渠道固定额度，座席回总池",
                                       'source': '截止结算', 'line': foreign.get('source_line', '')})
                lease = None
            if ticket is not None:
                state, detail = SOLD, '截止前已收款并出票，继续占用渠道旧额度'
            elif seat_pays:
                state, detail = PAID_PENDING, '截止前已收款，票号回执未到，仍占旧额度'
            elif lease is not None:
                state, detail = AWAIT, '截止时占座仍有效，空座暂留等待成交回执'
            else:
                state, detail = RETURNED, '截止前未成交，座席回收总池供临售'
            seat_ledger.append({'seat': seat, 'channel': channel, 'state': state, 'detail': detail,
                                'order': (ticket or (seat_pays[0] if seat_pays else None) or lease or {}).get('order', ''),
                                'lease': (ticket or (seat_pays[0] if seat_pays else None) or lease or {}).get('lease', '')})

    # 原批次所有被隔离的 pay/issue 都是仍需人工处理的回执；到达时已无有效占座的一律判 LATE_REJECT。
    late_rejects = []
    for q in quarantine:
        raw = q.get('raw') or {}
        if raw.get('type') not in ('pay', 'issue'):
            continue
        arrival_raw = raw.get('time')
        if arrival_raw is None:
            continue
        try:
            arrival = arrival_raw if isinstance(arrival_raw, datetime) else instant(arrival_raw)
        except DomainError:
            continue  # 时间本身无效的隔离行保留原原因码，不纳入回执裁决
        active = _active_lease(leases, raw.get('seat', ''), arrival)
        code = 'LATE_REJECT' if active is None else q['code']
        late_rejects.append({'id': raw.get('id', q.get('key', '')), 'seat': raw.get('seat', ''),
                             'order': raw.get('order', ''), 'channel': raw.get('channel', ''),
                             'type': raw['type'], 'time': arrival, 'amount': raw.get('amount', ''),
                             'ticket': raw.get('ticket', ''), 'accepted': False, 'code': code,
                             'reason': REASONS.get(code, code),
                             'detail': '过期占座后到达的回执，拒绝受理' if code == 'LATE_REJECT' else q.get('detail', ''),
                             'source': '原批次隔离', 'line': q.get('line', '')})

    channels = summarize(seat_ledger)
    receipts = quota_breaches + late_rejects
    totals = {'quota': sum(c['quota'] for c in channels), 'occupied': sum(c['occupied'] for c in channels),
              'pending': sum(c['pending'] for c in channels), 'returned': sum(c['returned'] for c in channels),
              'late_rejects': len(late_rejects), 'rejected': len(receipts)}
    if totals['occupied'] + totals['pending'] + totals['returned'] != totals['quota']:
        raise ValueError('截止结算席位不守恒')
    return {'deadline': deadline, 'seat_ledger': seat_ledger, 'channels': channels,
            'receipts': receipts, 'totals': totals}


def _find_seat(settlement, seat):
    return next((x for x in settlement['seat_ledger'] if x['seat'] == seat), None)


def _accepted_payments(settlement, payments):
    out = list(payments)
    for r in settlement['receipts']:
        if r['accepted'] and r['type'] == 'pay':
            out.append({**r,
                        'time': r['time'] if isinstance(r['time'], datetime) else instant(r['time']),
                        'amount': r['amount'] if isinstance(r['amount'], D) else D(str(r['amount']))})
    return out


def submit_receipt(settlement, leases, payments, tickets, receipt):
    # 同一事件号重放：直接回放首次裁决，绝不第二次扣减额度。
    for prior in settlement['receipts']:
        if prior['id'] == receipt['id']:
            return {**prior, 'replayed': True}

    base = {'id': receipt['id'], 'seat': receipt['seat'], 'order': receipt['order'],
            'channel': receipt['channel'], 'type': receipt['type'], 'time': receipt['time'],
            'amount': str(receipt.get('amount', '')), 'ticket': receipt.get('ticket', ''),
            'source': '截止后补传', 'line': receipt.get('line', '')}

    def reject(code, detail):
        record = {**base, 'accepted': False, 'code': code, 'reason': REASONS.get(code, code), 'detail': detail}
        settlement['receipts'].append(record)
        settlement['totals']['rejected'] = sum(1 for r in settlement['receipts'] if not r['accepted'])
        if code == 'LATE_REJECT':
            settlement['totals']['late_rejects'] = sum(1 for r in settlement['receipts']
                                                       if not r['accepted'] and r['code'] == 'LATE_REJECT')
        return record

    owner = next((name for name, seats in QUOTA.items() if receipt['seat'] in seats), None)
    if owner is None:
        return reject('UNMAPPED', '座席不在演出目录或渠道额度内')
    row = _find_seat(settlement, receipt['seat'])
    if row is None:
        return reject('UNMAPPED', '座席未参与本次截止结算')
    if receipt['channel'] != owner:
        return reject('CONFLICT', '回执渠道与该座席固定额度渠道不符')
    lease = _active_lease(leases, receipt['seat'], receipt['time'])
    if lease is None or lease['order'] != receipt['order']:
        return reject('LATE_REJECT', '过期占座后到达的回执，座席已回总池，拒绝重新占用')
    if lease['channel'] != receipt['channel']:
        return reject('CONFLICT', '回执渠道与占座租约渠道不符')

    amount = receipt.get('amount')
    if not isinstance(amount, D) or amount <= 0:
        return reject('NEGATIVE', '回执金额必须为正数')

    if receipt['type'] == 'pay':
        if row['state'] in OCCUPYING:
            return reject('DUPLICATE', '该座席已有成交支付，额度不得重复扣减')
        row['state'] = PAID_PENDING
        row['order'] = receipt['order']
        row['lease'] = lease['lease']
        row['detail'] = '截止后补传支付受理，回执落入有效占座区间，继续占用旧额度'
        record = {**base, 'lease': lease['lease'], 'accepted': True, 'code': 'PASS', 'reason': '受理',
                  'detail': '补传支付有效，座席转为成交待出票'}
    elif receipt['type'] == 'issue':
        if not receipt.get('ticket'):
            return reject('MISSING', '出票回执缺少票号')
        known_tickets = {t['ticket'] for t in tickets} | {r.get('ticket') for r in settlement['receipts'] if r.get('ticket')}
        if receipt['ticket'] in known_tickets:
            return reject('CONFLICT', '票号全场唯一，不得重复出票')
        matched = [p for p in _accepted_payments(settlement, payments)
                   if p['seat'] == receipt['seat'] and p['order'] == receipt['order']
                   and p['channel'] == receipt['channel'] and p['time'] <= receipt['time']]
        if len(matched) != 1:
            return reject('ORPHAN', '出票回执缺少匹配的有效支付')
        if matched[0]['amount'] != amount:
            return reject('CONFLICT', '票面金额与支付金额不符')
        row['state'] = SOLD
        row['order'] = receipt['order']
        row['lease'] = matched[0]['lease']
        row['detail'] = '截止后补传出票受理，成交闭环，继续占用渠道旧额度'
        record = {**base, 'accepted': True, 'code': 'PASS', 'reason': '受理',
                  'detail': '补传出票有效，座席转为成交已出票'}
    else:
        return reject('STATE', '回执事件类型仅支持 pay 或 issue')

    settlement['receipts'].append(record)
    settlement['channels'] = summarize(settlement['seat_ledger'])
    totals = settlement['totals']
    totals['occupied'] = sum(c['occupied'] for c in settlement['channels'])
    totals['pending'] = sum(c['pending'] for c in settlement['channels'])
    totals['returned'] = sum(c['returned'] for c in settlement['channels'])
    totals['rejected'] = sum(1 for r in settlement['receipts'] if not r['accepted'])
    totals['late_rejects'] = sum(1 for r in settlement['receipts']
                                 if not r['accepted'] and r['code'] == 'LATE_REJECT')
    return record
