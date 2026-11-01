"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    FETCH_RECORD = "fetch_record"
    PARSE_LOOSE = "parse_loose"
    NORMALIZE_FIELD = "normalize_field"
    REPAIR_KEY = "repair_key"


class Task(Enum):
    NORMALIZE_FIELD = "normalize-field"
    REPAIR_RECORD = "repair-record"


class FieldName(Enum):
    ORDER_ID = "order_id"
    EMAIL = "email"
    QUANTITY = "quantity"
    UNIT_PRICE = "unit_price"
    COUNTRY = "country"
    SHIP_DATE = "ship_date"
    EXPRESS = "express"


RECORD_ID = "The order record's id, e.g. R2-MESSY"
ORDER_ID = "The order id, ORD- and five digits, e.g. ORD-10002; empty when unfixable"
EMAIL = "The customer's email, lower case; empty when unfixable"
QUANTITY = "How many were ordered, 1 to 99; 0 when unfixable"
UNIT_PRICE_CENTS = "The price of one, in whole US cents, e.g. 1999 for $19.99; 0 when unfixable"
COUNTRY = "The ISO 3166 two-letter country code, e.g. US; empty when unfixable"
SHIP_DATE = "The ship date, YYYY-MM-DD; empty when unfixable"
EXPRESS = "Whether it ships express; false when unfixable"
UNFIXABLE = "Every field that is missing or cannot be normalized, in the order of FieldName"


@dataclass
class RecordInput(Output):
    record_id: Annotated[str, RECORD_ID]


@dataclass
class RawRecordOutput(Output):
    record_id: Annotated[str, RECORD_ID]
    raw: Annotated[str, "The record's text, exactly as stored"]


@dataclass
class ParseInput(Output):
    raw: Annotated[str, "A record's text"]


@dataclass
class RawField(Output):
    name: Annotated[str, "The field's name, as the record spells it"]
    raw: Annotated[str, "Its value as text, unnormalized"]


@dataclass
class ParseOutput(Output):
    readable: Annotated[bool, "Whether the text could be read as fields at all"]
    fields: Annotated[list[RawField], "Every field read, in the record's order; empty when unreadable"]
    note: Annotated[str, "How it was read, or why it could not be"]


@dataclass
class NormalizeInput(Output):
    field: Annotated[FieldName, "The field the value belongs to"]
    raw: Annotated[str, "The value as text, as parse_loose read it"]


@dataclass
class NormalizeOutput(Output):
    field: Annotated[FieldName, "The field"]
    ok: Annotated[bool, "Whether the value could be normalized"]
    value: Annotated[str, "The normalized value as text (cents for unit_price, true or false for express); empty when not ok"]
    reason: Annotated[str, "Which rule normalized it, or why none could"]


@dataclass
class RepairOutput(Output):
    order_id: Annotated[str, ORDER_ID]
    email: Annotated[str, EMAIL]
    quantity: Annotated[int, QUANTITY]
    unit_price_cents: Annotated[int, UNIT_PRICE_CENTS]
    country: Annotated[str, COUNTRY]
    ship_date: Annotated[str, SHIP_DATE]
    express: Annotated[bool, EXPRESS]
    unfixable: Annotated[list[FieldName], UNFIXABLE]


@dataclass
class RepairKeyOutput(Output):
    order_id: Annotated[str, ORDER_ID]
    email: Annotated[str, EMAIL]
    quantity: Annotated[int, QUANTITY]
    unit_price_cents: Annotated[int, UNIT_PRICE_CENTS]
    country: Annotated[str, COUNTRY]
    ship_date: Annotated[str, SHIP_DATE]
    express: Annotated[bool, EXPRESS]
    unfixable: Annotated[list[FieldName], UNFIXABLE]


TOOLS = {
    Tool.FETCH_RECORD: (RecordInput, RawRecordOutput),
    Tool.PARSE_LOOSE: (ParseInput, ParseOutput),
    Tool.NORMALIZE_FIELD: (NormalizeInput, NormalizeOutput),
    Tool.REPAIR_KEY: (RecordInput, RepairKeyOutput),
}
TASKS = {
    Task.NORMALIZE_FIELD: (NormalizeInput, NormalizeOutput),
    Task.REPAIR_RECORD: (RecordInput, RepairOutput),
}
