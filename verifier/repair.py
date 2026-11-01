"""Checks for the record tools and the repair-record task. Pure functions of their arguments."""

import re

from contract import FieldName

from .checks import result

COUNTRIES = {"US", "CA", "MX", "GB", "DE", "FR", "JP", "TW"}
CANONICAL = {
    FieldName.ORDER_ID: re.compile(r"^ORD-\d{5}$"),
    FieldName.EMAIL: re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$"),
    FieldName.QUANTITY: re.compile(r"^([1-9]|[1-9]\d)$"),
    FieldName.UNIT_PRICE: re.compile(r"^(0|[1-9]\d*)$"),
    FieldName.COUNTRY: re.compile(r"^(US|CA|MX|GB|DE|FR|JP|TW)$"),
    FieldName.SHIP_DATE: re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    FieldName.EXPRESS: re.compile(r"^(true|false)$"),
}
# Every field of a repaired record, the order unfixable lists them in.
FIELDS = list(FieldName)


def _calendar_date(text):
    year, month, day = (int(part) for part in text.split("-"))
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= month <= 12 and 1 <= day <= days[month - 1]


def canonical(field, value):
    """Whether ``value`` is ``field``'s normalized form."""
    if not CANONICAL[field].fullmatch(value):
        return False
    return field != FieldName.SHIP_DATE or _calendar_date(value)


def verify_record_input(value):
    problem = "record_id must not be blank" if not value.record_id.strip() else None
    return result(problem is None, problem or "input is valid")


def verify_parse_input(value):
    problem = "raw must not be blank" if not value.raw.strip() else None
    return result(problem is None, problem or "input is valid")


def verify_normalize_input(value):
    return result(True, "input is valid")


def verify_raw_output(input_value, output, workspace):
    if output.record_id != input_value.record_id:
        return result(False, f"fetched {output.record_id!r}, not {input_value.record_id!r}")
    if not output.raw.strip():
        return result(False, "the record is empty")
    return result(True, "the record is fetched")


def verify_parse_output(input_value, output, workspace):
    if not output.readable and output.fields:
        return result(False, "an unreadable record has no fields")
    names = [field.name for field in output.fields]
    if len(set(names)) != len(names):
        return result(False, "a field is read twice")
    if any(field.name not in input_value.raw for field in output.fields):
        return result(False, "a field name does not appear in the record")
    if not output.note.strip():
        return result(False, "the parse gives no note")
    return result(True, f"{len(names)} fields read" if output.readable else "correctly unreadable")


def _normalized_problem(field, ok, value):
    if ok and not canonical(field, value):
        return f"{value!r} is not a normalized {field.value}"
    if not ok and value:
        return f"{field.value} could not be normalized, so its value must be empty"
    return None


def verify_normalize_output(input_value, output, workspace):
    if output.field != input_value.field:
        return result(False, f"normalized {output.field.value}, not {input_value.field.value}")
    if not input_value.raw.strip() and output.ok:
        return result(False, "an empty value cannot be normalized")
    problem = _normalized_problem(output.field, output.ok, output.value)
    if problem is None and not output.reason.strip():
        problem = "the normalization gives no reason"
    return result(problem is None, problem or f"{output.field.value}: {output.value or 'unfixable'}")


def _values(record):
    """Each field's value in the repaired record, as normalize_field writes it."""
    return {
        FieldName.ORDER_ID: record.order_id,
        FieldName.EMAIL: record.email,
        FieldName.QUANTITY: str(record.quantity) if record.quantity else "",
        FieldName.UNIT_PRICE: str(record.unit_price_cents),
        FieldName.COUNTRY: record.country,
        FieldName.SHIP_DATE: record.ship_date,
        FieldName.EXPRESS: "true" if record.express else "false",
    }


def verify_key_output(input_value, output, workspace):
    values = _values(output)
    for field in FIELDS:
        if field not in output.unfixable and not canonical(field, values[field]):
            return result(False, f"{field.value} is neither normalized nor unfixable")
    return result(True, "the key is consistent")


def verify_repair(arguments, output, reference, workspace):
    if reference is None:
        return result(False, "there is no repair key to judge against")
    given, expected = _values(output), _values(reference)
    given_unfixable, expected_unfixable = set(output.unfixable), set(reference.unfixable)
    wrong = []
    for field in FIELDS:
        if field in expected_unfixable:
            placeholder = {FieldName.UNIT_PRICE: "0", FieldName.EXPRESS: "false"}.get(field, "")
            if field not in given_unfixable or given[field] != placeholder:
                wrong.append(field.value)
        elif field in given_unfixable or given[field] != expected[field]:
            wrong.append(field.value)
    if len(output.unfixable) != len(given_unfixable):
        wrong.append("unfixable lists a field twice")
    score = (len(FIELDS) - len([w for w in wrong if w in {f.value for f in FIELDS}])) / len(FIELDS)
    if wrong:
        return result(False, f"wrong: {', '.join(wrong)}", score=score,
                      expected={field.value: expected[field] for field in FIELDS},
                      expected_unfixable=[field.value for field in reference.unfixable])
    return result(True, f"every field is repaired; unfixable: {[f.value for f in reference.unfixable] or 'none'}")
