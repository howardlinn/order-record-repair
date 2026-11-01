from __future__ import annotations

from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import TASKS, TOOLS, NormalizeInput, ParseInput, RecordInput, RepairKeyOutput, RepairOutput, Task, Tool
from plugin import fetch_record, normalize_field, parse_loose, repair_key


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def verify_input(tool: str, value: dict) -> dict:
    return verifier.verify_input(tool, build_output(value, TOOLS[Tool(tool)][0]))


def verify_output(tool: str, given: dict, made: dict, workspace: Path) -> dict:
    classes = TOOLS[Tool(tool)]
    return verifier.verify_output(tool, build_output(given, classes[0]), build_output(made, classes[1]), str(workspace))


def key(record_id: str, workspace: Path) -> dict:
    return plain_output(repair_key(RecordInput(record_id=record_id), workspace))


def judge(record_id: str, output: dict, workspace: Path, pinned="key") -> dict:
    reference = build_output(key(record_id, workspace), RepairKeyOutput) if pinned == "key" else pinned
    return verifier.verify_task("repair-record", build_output({"record_id": record_id}, RecordInput),
                                build_output(output, RepairOutput), reference, str(workspace))


EXPECTED = {
    "R1-CLEAN": ("ORD-10001", "ana@example.com", 2, 1999, "US", "2026-12-18", False, []),
    "R2-MESSY": ("ORD-10002", "ben.li@example.com", 3, 125050, "US", "2026-12-18", True, []),
    "R3-EDGES": ("", "carla@example.com", 0, 0, "CA", "2028-02-29", False, ["order_id", "quantity"]),
    "R4-MISSING": ("ORD-10004", "dev@example.org", 1, 0, "", "", True, ["unit_price", "country", "ship_date"]),
    "R5-LINES": ("ORD-10005", "eve@shop.co.uk", 99, 700, "GB", "", True, ["ship_date"]),
    "R6-BROKEN": ("ORD-10006", "", 0, 0, "JP", "", False, ["email", "quantity", "unit_price", "ship_date"]),
    "R7-TRICKY": ("ORD-10007", "gina@example.com", 0, 0, "MX", "2026-12-01", False, ["quantity", "unit_price", "express"]),
    "R8-UNREADABLE": ("", "", 0, 0, "", "", False,
                      ["order_id", "email", "quantity", "unit_price", "country", "ship_date", "express"]),
}
NAMES = ("order_id", "email", "quantity", "unit_price_cents", "country", "ship_date", "express", "unfixable")


@pytest.mark.parametrize("record_id", sorted(EXPECTED))
def test_key_follows_the_rules_and_is_accepted(tmp_path: Path, record_id: str) -> None:
    expected = dict(zip(NAMES, EXPECTED[record_id], strict=True))
    assert key(record_id, tmp_path) == expected
    assert judge(record_id, expected, tmp_path)["valid"] is True


def test_unfixable_may_be_listed_in_any_order(tmp_path: Path) -> None:
    output = key("R6-BROKEN", tmp_path)
    assert judge("R6-BROKEN", output | {"unfixable": list(reversed(output["unfixable"]))}, tmp_path)["valid"] is True


@pytest.mark.parametrize(
    ("record_id", "changes", "wrong"),
    [
        ("R2-MESSY", {"unit_price_cents": 1250}, "unit_price"),  # read $1,250.5 as 12.50
        ("R2-MESSY", {"unit_price_cents": 125005}, "unit_price"),  # .5 is 50 cents, not 5
        ("R2-MESSY", {"email": " Ben.Li@Example.COM "}, "email"),  # not normalized
        ("R2-MESSY", {"ship_date": "2026-18-12"}, "ship_date"),  # read as day/month
        ("R2-MESSY", {"order_id": "ord 10002"}, "order_id"),
        ("R3-EDGES", {"order_id": "ORD-01003"}, "order_id"),  # invented a digit
        ("R3-EDGES", {"unfixable": ["order_id", "quantity", "unit_price"]}, "unit_price"),  # $0 is a valid price
        ("R5-LINES", {"ship_date": "2027-02-28", "unfixable": []}, "ship_date"),  # guessed a date for Feb 29, 2027
        ("R5-LINES", {"ship_date": "2027-03-01", "unfixable": []}, "ship_date"),
        ("R6-BROKEN", {"quantity": 99, "unfixable": ["email", "unit_price", "ship_date"]}, "quantity"),  # clamped 100
        ("R7-TRICKY", {"unit_price_cents": 399, "unfixable": ["quantity", "express"]}, "unit_price"),  # 3,99 guessed
        ("R7-TRICKY", {"quantity": 2}, "quantity"),  # unfixable, but a value is filled in
        ("R8-UNREADABLE", {"order_id": "ORD-10008", "unfixable": ["email", "quantity", "unit_price", "country",
                                                                  "ship_date", "express"]}, "order_id"),
        ("R1-CLEAN", {"unfixable": ["express"]}, "express"),  # gave up on a fine field
    ],
)
def test_rejects_wrong_repairs(tmp_path: Path, record_id: str, changes: dict, wrong: str) -> None:
    verdict = judge(record_id, key(record_id, tmp_path) | changes, tmp_path)
    assert verdict["valid"] is False and wrong in verdict["message"]
    assert verdict["score"] < 1.0


def test_rejects_a_duplicate_unfixable_field(tmp_path: Path) -> None:
    output = key("R5-LINES", tmp_path)
    assert judge("R5-LINES", output | {"unfixable": ["ship_date", "ship_date"]}, tmp_path)["valid"] is False


def test_rejects_a_verdict_without_a_reference(tmp_path: Path) -> None:
    assert judge("R1-CLEAN", key("R1-CLEAN", tmp_path), tmp_path, None)["valid"] is False


def test_score_counts_the_fields_right(tmp_path: Path) -> None:
    output = key("R2-MESSY", tmp_path) | {"email": "x@y.zz", "country": "CA"}
    assert judge("R2-MESSY", output, tmp_path)["score"] == pytest.approx(5 / 7)


@pytest.mark.parametrize(
    ("field", "raw", "value"),
    [
        ("order_id", "ord_10002", "ORD-10002"),
        ("order_id", "12345", "ORD-12345"),
        ("order_id", "ORD-123456", ""),
        ("email", "MAILTO:A@B.CO", "a@b.co"),
        ("email", "a@b", ""),
        ("quantity", "1", "1"),
        ("quantity", "99", "99"),
        ("quantity", "0", ""),
        ("quantity", "3.00", "3"),
        ("unit_price", "USD 7", "700"),
        ("unit_price", "$0.05", "5"),
        ("unit_price", "12.345", ""),
        ("unit_price", "1,000,000", "100000000"),
        ("country", "U.S.A.", "US"),
        ("country", "Atlantis", ""),
        ("ship_date", "2/29/2028", "2028-02-29"),
        ("ship_date", "2/29/2027", ""),
        ("ship_date", "Sept 1, 2026", ""),
        ("ship_date", "Sep 1, 2026", "2026-09-01"),
        ("express", "Y", "true"),
        ("express", "maybe", ""),
        ("express", "   ", ""),
    ],
)
def test_normalization_rules(tmp_path: Path, field: str, raw: str, value: str) -> None:
    given = {"field": field, "raw": raw}
    made = plain_output(normalize_field(build_output(given, NormalizeInput), tmp_path))
    assert made["value"] == value and made["ok"] is bool(value)
    assert verify_output("normalize_field", given, made, tmp_path)["valid"] is True
    assert verifier.verify_task("normalize-field", build_output(given, NormalizeInput),
                                build_output(made, TASKS[Task.NORMALIZE_FIELD][1]), None, str(tmp_path))["valid"]


@pytest.mark.parametrize(
    ("given", "made"),
    [
        ({"field": "ship_date", "raw": "x"}, {"field": "ship_date", "ok": True, "value": "2027-02-29", "reason": "r"}),
        ({"field": "country", "raw": "x"}, {"field": "country", "ok": True, "value": "usa", "reason": "r"}),
        ({"field": "quantity", "raw": "x"}, {"field": "quantity", "ok": True, "value": "100", "reason": "r"}),
        ({"field": "email", "raw": "x"}, {"field": "email", "ok": False, "value": "x", "reason": "r"}),
        ({"field": "email", "raw": "x"}, {"field": "express", "ok": False, "value": "", "reason": "r"}),
        ({"field": "email", "raw": " "}, {"field": "email", "ok": True, "value": "a@b.co", "reason": "r"}),
    ],
)
def test_rejects_inconsistent_normalizations(tmp_path: Path, given: dict, made: dict) -> None:
    assert verify_output("normalize_field", given, made, tmp_path)["valid"] is False


def test_parse_reads_every_format(tmp_path: Path) -> None:
    for record_id, readable in (("R2-MESSY", True), ("R4-MISSING", True), ("R5-LINES", True), ("R8-UNREADABLE", False)):
        raw = fetch_record(RecordInput(record_id=record_id), tmp_path).raw
        made = plain_output(parse_loose(ParseInput(raw=raw), tmp_path))
        assert made["readable"] is readable
        assert verify_output("parse_loose", {"raw": raw}, made, tmp_path)["valid"] is True
    bad = {"readable": False, "fields": [{"name": "email", "raw": "a"}], "note": "n"}
    assert verify_output("parse_loose", {"raw": "email: a"}, bad, tmp_path)["valid"] is False
    invented = {"readable": True, "fields": [{"name": "phone", "raw": "1"}], "note": "n"}
    assert verify_output("parse_loose", {"raw": "email: a"}, invented, tmp_path)["valid"] is False


def test_inputs_and_fetch(tmp_path: Path) -> None:
    assert verify_input("fetch_record", {"record_id": " "})["valid"] is False
    assert verify_input("parse_loose", {"raw": ""})["valid"] is False
    assert verify_input("repair_key", {"record_id": "R1-CLEAN"})["valid"] is True
    made = plain_output(fetch_record(RecordInput(record_id="R1-CLEAN"), tmp_path))
    assert verify_output("fetch_record", {"record_id": "R1-CLEAN"}, made, tmp_path)["valid"] is True
    assert verify_output("fetch_record", {"record_id": "R2-MESSY"}, made, tmp_path)["valid"] is False
    with pytest.raises(ValueError, match="no record"):
        fetch_record(RecordInput(record_id="R9"), tmp_path)


def test_key_output_consistency(tmp_path: Path) -> None:
    made = key("R3-EDGES", tmp_path)
    assert verify_output("repair_key", {"record_id": "R3-EDGES"}, made, tmp_path)["valid"] is True
    assert verify_output("repair_key", {"record_id": "R3-EDGES"}, made | {"unfixable": []}, tmp_path)["valid"] is False
