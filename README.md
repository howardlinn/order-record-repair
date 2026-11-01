# Order Record Repair

A NanoAgent plugin with a verifiable data-cleaning task: an agent repairs a messy order record into a strict
schema, field by field, by fixed normalization rules, and marks the fields that cannot be repaired.

The schema: `order_id` (`ORD-` and five digits), `email` (lower case), `quantity` (1 to 99),
`unit_price_cents` (whole cents), `country` (ISO two-letter code), `ship_date` (`YYYY-MM-DD`, a real calendar
date) and `express` (true or false), plus `unfixable`, the fields that are missing or break the rules.

The rules are code (`normalize_field`), so every record has exactly one right repair. Some of them:

| Field | Repaired | Unfixable |
|---|---|---|
| `order_id` | `ord 10002`, `ORD#10005`, `10006` → `ORD-…` | four or six digits |
| `email` | trimmed, lower-cased, `mailto:` dropped | no domain suffix, `(at)` |
| `quantity` | `3`, `3.00` | `0`, `100`, `2.5` |
| `unit_price` | `$1,250.5` → 125050, `USD 7` → 700, `0` → 0 | `12.345`, `-5.00`, `3,99` (ambiguous) |
| `country` | `usa`, `U.K.`, `México` | unknown names |
| `ship_date` | `12/18/2026` (US order), `December 1, 2026`, `2/29/2028` | `2027-02-29`, month 13 |
| `express` | `yes`, `N`, `1`, `TRUE` | `maybe`, empty |

The records are a fixed set bundled with the plugin (`src/plugin/data/records.json`): clean, messy, loose
JSON, name-value lines, missing fields, boundary values and one record that is not readable at all. The
verifier compares every field and the unfixable set with the reference repair, scores the share of fields
right, and is valid only when all seven are.

## Tools

| Tool | Does | Code |
|---|---|---|
| `fetch_record` | Fetches a record's text, exactly as stored | `src/plugin/repair.py` |
| `parse_loose` | Reads the text as fields, tolerating loose JSON and name-value lines | `src/plugin/repair.py` |
| `normalize_field` | Normalizes one field's value by the rules, or says why it cannot | `src/plugin/repair.py` |
| `repair_key` | The fully repaired record: the reference, run out of the agent's sight | `src/plugin/repair.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `normalize-field` | Normalizes one value of an order field | `tool`, with `normalize_field` |
| `repair-record` | Repairs a messy record into the schema | `agent`, with `fetch_record`, `parse_loose` and `normalize_field`; reference `repair_key` |

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # needed environment variable names (none)
├── src/plugin/      # the MCP server, the tools (repair.py) and the bundled data/records.json
├── tests/           # test_verifier.py: correct, wrong, missing, malformed and boundary cases
├── ui/              # renderers.js: outputs drawn from their JSON Schema
├── product/         # product.yaml and icon.svg
└── verifier/        # deterministic verifier: repair.py, on contract instances, standard library only
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

The plugin needs no network and no environment variables.
