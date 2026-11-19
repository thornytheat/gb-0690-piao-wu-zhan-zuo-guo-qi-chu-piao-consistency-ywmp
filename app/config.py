from pathlib import Path
TITLE = '票务占座过期与出票一致性'
SHORT = 'seat-expiry'
STAGES = ['receive', 'seats', 'leases', 'payments', 'tickets', 'reconcile', 'replay', 'settlement']
MODULES = ['渠道接收', '座席映射', '租约回放', '支付归属', '出票核验', '渠道对账', '补传复核', '额度结算']
COLUMNS = {'id': '事件号', 'channel': '渠道', 'seat': '座席', 'order': '订单', 'time': '时刻 UTC', 'type': '事件', 'expires': '到期 UTC', 'version': '版本', 'state': '状态', 'payment': '支付状态', 'ticket': '票号', 'reason': '原因', 'code': '原因码', 'line': '行号', 'count': '数量', 'lease': '租约号', 'amount': '金额 CNY', 'key': '业务键', 'detail': '依据', 'late_minutes': '迟到 min'}
DEFAULTS = {'observation_end': '2026-11-18T00:00:00+08:00', 'late_minutes': '10', 'settle_deadline': '2026-11-17T10:42:00+08:00'}
RULE_VERSION = "2026.11.19-v1"
SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
MAX_BYTES = 4 * 1024 * 1024
# 渠道开售前分到的固定座席额度（按渠道分座凭证逐席登记），截止结算只在该额度内逐席裁决
QUOTA = {
    '官方': ['A-01', 'A-04', 'A-07', 'A-10', 'A-13', 'A-15'],
    '票社': ['A-02', 'A-05', 'A-08', 'A-11', 'A-14', 'A-16'],
    '团购': ['A-03', 'A-06', 'A-09', 'A-12'],
}

COLUMNS.update({'start':'占座起 UTC','end':'租约止 UTC','paid':'支付 CNY','ticketed':'出票 CNY','delta':'悬单 CNY','payments':'支付笔','tickets':'出票笔'})
COLUMNS.update({'deadline':'截止时刻 UTC','quota':'固定额度','occupied':'仍占旧额度','returned':'已回总池','pending':'回执待处理','decision':'裁决'})
