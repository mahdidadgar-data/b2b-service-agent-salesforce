"""
Pre-flight check: validate the generated data against the org BEFORE loading it.

Why: a bulk insert with allOrNone fails as a whole, and most records then only show
ALL_OR_NONE_OPERATION_ROLLED_BACK. This script finds every problem in one run, without
writing anything, by comparing each value in data/generated/*.json with the org's own
field definitions (`sf sobject describe`):
  - the field exists and can be set on insert
  - text values fit the field length
  - picklist values exist in the org's picklist

Read-only. All calls go through the Salesforce CLI; no token is handled.

Run:  python data/preflight.py              (checks against the default org)
      python data/preflight.py --org delta-dev
Exit code 0 = no problems, 1 = problems found (fix the generator, regenerate, re-check).
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "generated"
SF = shutil.which("sf") or "sf"
TEXT_TYPES = ("string", "textarea", "phone", "email", "url")
FILES = {"Product2": "products", "Account": "accounts", "Contact": "contacts",
         "Order": "orders", "Case": "cases", "Opportunity": "opportunities"}


def describe(sobject, org_args):
    """Return {field name: field describe} for one object."""
    result = subprocess.run([SF, "sobject", "describe", "--sobject", sobject, "--json", *org_args],
                            capture_output=True, text=True, encoding="utf-8")
    out = result.stdout
    data = json.loads(out[out.find("{"):])
    if data.get("status") != 0:
        sys.exit(f"Describe {sobject} failed: {data.get('message')}")
    return {f["name"]: f for f in data["result"]["fields"]}


def check_record(sobject, record, fields):
    """Yield a problem description for every invalid value in one record."""
    for name, value in record.items():
        if name.startswith("_") or value is None:  # helper keys and empty values are not sent
            continue
        field = fields.get(name)
        if field is None:
            yield f"{name}: field does not exist (or is not visible: check field-level security)"
            continue
        if not field["createable"]:
            yield f"{name}: field cannot be set on insert"
        if field["type"] in TEXT_TYPES and len(str(value)) > field["length"]:
            yield f"{name}: {len(str(value))} characters > max {field['length']}: {str(value)[:60]!r}"
        if field["type"] == "picklist":
            allowed = {p["value"] for p in field["picklistValues"] if p["active"]}
            if value not in allowed:
                kind = "restricted" if field.get("restrictedPicklist") else "unrestricted"
                yield f"{name}: {value!r} is not a value of this {kind} picklist {sorted(allowed)}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="Org alias (default: the CLI default org)")
    args = parser.parse_args()
    org_args = ["--target-org", args.org] if args.org else []

    problems = 0
    for sobject, filename in FILES.items():
        records = json.loads((DATA_DIR / f"{filename}.json").read_text(encoding="utf-8"))
        fields = describe(sobject, org_args)
        for record in records:
            for problem in check_record(sobject, record, fields):
                print(f"  {sobject}.{problem}")
                problems += 1
        print(f"checked {sobject:<12} {len(records):>3} records")

    print(f"\n{problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
