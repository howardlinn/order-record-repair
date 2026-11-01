"""Reading and normalizing order records: the bundled records (data/records.json) and the fixed rules."""

import calendar
import json
import re
from pathlib import Path

from contract import (
    FieldName,
    NormalizeInput,
    NormalizeOutput,
    ParseInput,
    ParseOutput,
    RawField,
    RawRecordOutput,
    RecordInput,
    RepairKeyOutput,
)

RECORDS = json.loads((Path(__file__).parent / "data" / "records.json").read_text(encoding="utf-8"))
LINE = re.compile(r"^\s*([A-Za-z_]\w*)\s*:\s*(.*?)\s*$")
EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
COUNTRIES = {
    "US": {"us", "usa", "united states", "united states of america"},
    "CA": {"ca", "can", "canada"},
    "MX": {"mx", "mex", "mexico", "méxico"},
    "GB": {"gb", "uk", "united kingdom", "great britain"},
    "DE": {"de", "germany", "deutschland"},
    "FR": {"fr", "france"},
    "JP": {"jp", "japan"},
    "TW": {"tw", "taiwan"},
}
MONTHS = {name.casefold(): number for number, name in enumerate(calendar.month_name) if name}
MONTHS |= {name.casefold(): number for number, name in enumerate(calendar.month_abbr) if name}
TRUE, FALSE = {"true", "yes", "y", "t", "1"}, {"false", "no", "n", "f", "0"}


def _text(value):
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value)


def parse(raw):
    """(fields as [(name, raw)], note), or (None, why) when the text is not a record."""
    text = raw.strip()
    if text.startswith("{"):
        fixed = re.sub(r",\s*}", "}", text)
        if "'" in fixed and '"' not in fixed:
            fixed = fixed.replace("'", '"')
        fixed = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', fixed)
        try:
            data = json.loads(fixed)
        except json.JSONDecodeError as error:
            return None, f"not JSON even after loosening: {error.msg}"
        if not isinstance(data, dict):
            return None, "the JSON is not an object"
        note = "read as JSON" if fixed == text else "read as loose JSON (quotes, keys or a trailing comma fixed)"
        return [(name, _text(value)) for name, value in data.items()], note
    lines = [line for line in text.splitlines() if line.strip()]
    matches = [LINE.fullmatch(line) for line in lines]
    if lines and all(matches):
        return [(match.group(1), match.group(2)) for match in matches], "read as name: value lines"
    return None, "neither JSON nor name: value lines"


def _date(text):
    text = text.strip()
    if match := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text):
        year, month, day = (int(part) for part in match.groups())
    elif match := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text):
        month, day, year = (int(part) for part in match.groups())
    elif match := re.fullmatch(r"([A-Za-z]+)\.? (\d{1,2}),? (\d{4})", text):
        if match.group(1).casefold() not in MONTHS:
            return None, f"{match.group(1)!r} is not a month"
        month, day, year = MONTHS[match.group(1).casefold()], int(match.group(2)), int(match.group(3))
    else:
        return None, "not YYYY-MM-DD, MM/DD/YYYY or Month D, YYYY"
    if not 1 <= month <= 12 or not 1 <= day <= calendar.monthrange(year, month)[1]:
        return None, f"{year}-{month:02d}-{day:02d} is not a calendar date"
    return f"{year:04d}-{month:02d}-{day:02d}", "a calendar date"


def normalize(field, raw):
    """(value, reason), the value None when no rule normalizes ``raw``."""
    text = raw.strip()
    if not text:
        return None, "the value is empty"
    match field:
        case FieldName.ORDER_ID:
            if found := re.fullmatch(r"(?:ORD[\s#_-]*)?(\d{5})", text.upper()):
                return f"ORD-{found.group(1)}", "ORD- and the five digits"
            return None, "not ORD and five digits"
        case FieldName.EMAIL:
            email = text.casefold().removeprefix("mailto:")
            return (email, "lower-cased") if EMAIL.fullmatch(email) else (None, "not a full email address")
        case FieldName.QUANTITY:
            if not re.fullmatch(r"\d+(\.0+)?", text):
                return None, "not a whole number"
            number = int(text.split(".")[0])
            return (str(number), "a whole number") if 1 <= number <= 99 else (None, "outside 1 to 99")
        case FieldName.UNIT_PRICE:
            amount = re.sub(r"^(\$|USD)\s*", "", text, flags=re.IGNORECASE)
            if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d{1,2})?", amount):
                amount = amount.replace(",", "")
            if not re.fullmatch(r"\d+(\.\d{1,2})?", amount):
                return None, "not a non-negative amount with at most two decimals"
            dollars, _, cents = amount.partition(".")
            return str(int(dollars) * 100 + int(cents.ljust(2, "0"))), "dollars to cents"
        case FieldName.COUNTRY:
            name = text.casefold().replace(".", "").strip()
            for code, names in COUNTRIES.items():
                if name in names:
                    return code, "a known country name or code"
            return None, "not a known country"
        case FieldName.SHIP_DATE:
            return _date(text)
        case FieldName.EXPRESS:
            flag = text.casefold()
            if flag in TRUE or flag in FALSE:
                return ("true" if flag in TRUE else "false"), "a yes or no"
            return None, "not a yes or no"


def repair(raw):
    fields, _ = parse(raw)
    values = dict(fields or [])
    repaired, unfixable = {}, []
    for field in FieldName:
        value, _ = normalize(field, values.get(field.value, ""))
        if value is None:
            unfixable.append(field)
        repaired[field] = value
    return repaired, unfixable


def fetch_record(value: RecordInput, workspace: Path) -> RawRecordOutput:
    if value.record_id not in RECORDS:
        raise ValueError(f"no record {value.record_id!r}; known: {', '.join(sorted(RECORDS))}")
    return RawRecordOutput(record_id=value.record_id, raw=RECORDS[value.record_id])


def parse_loose(value: ParseInput, workspace: Path) -> ParseOutput:
    fields, note = parse(value.raw)
    if fields is None:
        return ParseOutput(readable=False, fields=[], note=note)
    return ParseOutput(readable=True, fields=[RawField(name=name, raw=raw) for name, raw in fields], note=note)


def normalize_field(value: NormalizeInput, workspace: Path) -> NormalizeOutput:
    normalized, reason = normalize(value.field, value.raw)
    return NormalizeOutput(field=value.field, ok=normalized is not None, value=normalized or "", reason=reason)


def repair_key(value: RecordInput, workspace: Path) -> RepairKeyOutput:
    repaired, unfixable = repair(fetch_record(value, workspace).raw)
    return RepairKeyOutput(
        order_id=repaired[FieldName.ORDER_ID] or "",
        email=repaired[FieldName.EMAIL] or "",
        quantity=int(repaired[FieldName.QUANTITY] or 0),
        unit_price_cents=int(repaired[FieldName.UNIT_PRICE] or 0),
        country=repaired[FieldName.COUNTRY] or "",
        ship_date=repaired[FieldName.SHIP_DATE] or "",
        express=repaired[FieldName.EXPRESS] == "true",
        unfixable=unfixable,
    )
