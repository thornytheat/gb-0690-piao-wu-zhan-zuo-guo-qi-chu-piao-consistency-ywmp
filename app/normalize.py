import csv, io, unicodedata
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from app.errors import DomainError
SENTINELS={"", "-", "N/A", "NULL", "未知"}
def number(value, nullable=False):
    value=unicodedata.normalize("NFKC", str(value)).strip()
    if value.upper() in SENTINELS or value in SENTINELS:
        if nullable: return None
        raise DomainError("MISSING","缺少必填数值")
    try:
        result=Decimal(value.replace(",", ""))
    except InvalidOperation:
        raise DomainError("NUMBER","数值格式错误")
    if not result.is_finite(): raise DomainError("NUMBER","数值必须有限")
    return result
def instant(value):
    try: result=datetime.fromisoformat(str(value).strip().replace("Z","+00:00"))
    except (ValueError,TypeError): raise DomainError("TIME","时间格式错误")
    if result.tzinfo is None: raise DomainError("TIME","时间必须包含偏移")
    return result.astimezone(timezone.utc)
def decode(raw):
    for encoding in ("utf-8-sig","gb18030"):
        try: return raw.decode(encoding),encoding
        except UnicodeDecodeError: pass
    raise DomainError("ENCODING","编码无法读取")
def rows_from(raw, required):
    from app.config import MAX_BYTES
    from app.reasons import rejected
    if len(raw)>MAX_BYTES: raise DomainError("TOO_LARGE","文件超过4MB",413)
    text,encoding=decode(raw)
    if not text: raise DomainError("EMPTY","文件没有数据")
    if not text.strip(): raise DomainError("BLANK_ONLY","仅含空行")
    reader=csv.reader(io.StringIO(text,newline=""),strict=True)
    try: header=next(reader)
    except (StopIteration,csv.Error): raise DomainError("HEADER","字段名读取失败")
    header=[v.strip().lstrip("\ufeff") for v in header]
    if len(header)!=len(set(header)) or not set(required)<=set(header):
        raise DomainError("HEADER","字段名不符合契约")
    good=[];quarantine=[];blank=0;total=0
    try:
        for cells in reader:
            if not cells or not any(v.strip() for v in cells): blank+=1;continue
            total+=1
            if len(cells)!=len(header):
                quarantine.append(rejected({"_line":reader.line_num},"COLUMN_COUNT",repr(cells)));continue
            row=dict(zip(header,(v.strip() for v in cells)));row["_line"]=reader.line_num
            good.append(row)
    except csv.Error: raise DomainError("CSV","CSV引号未闭合")
    if total==0: raise DomainError("HEADER_ONLY","只有字段名")
    return {"raw":good,"quarantine":quarantine,"input_count":total,"blank_count":blank,"encoding":encoding}
def serial(value):
    if isinstance(value,Decimal): return str(value)
    if isinstance(value,datetime): return value.isoformat()
    if isinstance(value,dict): return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [serial(v) for v in value]
    return value
