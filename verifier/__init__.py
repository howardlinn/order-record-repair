"""The deterministic verifier: each tool's checks live in repair.py, on contract instances."""

from contract import Task, Tool

from . import repair

INPUTS = {
    Tool.FETCH_RECORD: repair.verify_record_input,
    Tool.PARSE_LOOSE: repair.verify_parse_input,
    Tool.NORMALIZE_FIELD: repair.verify_normalize_input,
    Tool.REPAIR_KEY: repair.verify_record_input,
}
OUTPUTS = {
    Tool.FETCH_RECORD: repair.verify_raw_output,
    Tool.PARSE_LOOSE: repair.verify_parse_output,
    Tool.NORMALIZE_FIELD: repair.verify_normalize_output,
    Tool.REPAIR_KEY: repair.verify_key_output,
}


def _normalize_field(arguments, output, reference, workspace):
    return repair.verify_normalize_output(arguments, output, workspace)


# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {
    Task.NORMALIZE_FIELD: _normalize_field,
    Task.REPAIR_RECORD: repair.verify_repair,
}


def verify_input(tool, value):
    return INPUTS[Tool(tool)](value)


def verify_output(tool, input_value, output_value, workspace):
    return OUTPUTS[Tool(tool)](input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
