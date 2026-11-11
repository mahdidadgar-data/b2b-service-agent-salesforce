"""
API tests for the Get_Order_Status flow (agent action for UC1: order status).

Calls the flow the same way an agent or integration does: through the REST invocable-action
endpoint (/actions/custom/flow/Get_Order_Status). Every call goes through the Salesforce CLI
(`sf api request rest`), so no token is handled here.

Request bodies:  tests/flows/get_order_status/*.json
Ground truth:    data/generated/orders.json (the data that was loaded into the org)

What is tested:
  a) own order             -> found, with the status, date and delay reason from the data
  b) other company's order -> not found (guardrail: account filter)
  c) unknown customer      -> not found, with exactly the same message as b)
  d) empty customer number -> not found (guardrail must not depend on the input being filled)
For every "not found" case, no order details may be returned (no information leak).

Run:  python tests/run_flow_tests.py              (default org)
      python tests/run_flow_tests.py --org delta-dev
Exit code 0 = all tests passed, 1 = at least one failure.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "tests" / "flows" / "get_order_status"
ORDERS = {o["Name"]: o for o in json.loads((ROOT / "data" / "generated" / "orders.json").read_text(encoding="utf-8"))}
ENDPOINT = "/services/data/v62.0/actions/custom/flow/Get_Order_Status"
SF = shutil.which("sf") or "sf"

NOT_FOUND = "No order found for this customer number and order number. Please check both numbers."
DETAIL_FIELDS = ("deliveryStatus", "expectedDeliveryDate", "carrier", "trackingNumber", "delayReason")


def call_flow(body_file, org_args):
    """POST one request body to the invocable action; return the outputValues of the first result."""
    result = subprocess.run([SF, "api", "request", "rest", ENDPOINT, "--method", "POST",
                             "--body", f"@{body_file}", *org_args],
                            capture_output=True, text=True, encoding="utf-8")
    out = result.stdout
    starts = [i for i in (out.find("["), out.find("{")) if i != -1]
    if not starts:
        raise RuntimeError(f"No JSON in CLI output: {(out + result.stderr)[:500]}")
    response = json.loads(out[min(starts):])
    if not isinstance(response, list) or not response[0].get("isSuccess"):
        raise RuntimeError(f"Flow call failed: {json.dumps(response)[:500]}")
    return response[0]["outputValues"]


def expect_found(out, order_name):
    order = ORDERS[order_name]
    checks = [
        ("orderFound is true", out.get("orderFound") is True),
        ("deliveryStatus matches data", out.get("deliveryStatus") == order["Delivery_Status__c"]),
        ("expectedDeliveryDate matches data",
         (out.get("expectedDeliveryDate") or "")[:10] == order["Expected_Delivery_Date__c"]),
        ("delayReason matches data", out.get("delayReason") == order["Delay_Reason__c"]),
        ("message is empty", out.get("message") is None),
    ]
    return checks


def expect_not_found(out):
    checks = [
        ("orderFound is false", out.get("orderFound") is False),
        ("standard not-found message", out.get("message") == NOT_FOUND),
    ]
    checks += [(f"{f} not returned", out.get(f) is None) for f in DETAIL_FIELDS]
    return checks


TESTS = [
    ("a_own_order.json", "C-1004 + SO-10447: own order", lambda o: expect_found(o, "SO-10447")),
    ("b_other_company_order.json", "C-1001 + SO-10447: other company's order", expect_not_found),
    ("c_unknown_customer.json", "C-9999 + SO-10447: unknown customer", expect_not_found),
    ("d_empty_customer.json", "empty customer + SO-10447", expect_not_found),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="Org alias (default: the CLI default org)")
    args = parser.parse_args()
    org_args = ["--target-org", args.org] if args.org else []

    failures = 0
    outputs = {}
    for filename, title, expectations in TESTS:
        try:
            out = call_flow(CASES_DIR / filename, org_args)
            checks = expectations(out)
        except Exception as exc:  # noqa: BLE001  (report and count as a failure)
            out, checks = {}, [(f"call succeeded ({exc})", False)]
        outputs[filename] = out
        failed = [name for name, ok in checks if not ok]
        failures += bool(failed)
        print(f"{'PASS' if not failed else 'FAIL'}  {title}")
        for name in failed:
            print(f"        failed: {name}")
        shown = {k: v for k, v in out.items() if not k.startswith("Flow__")}
        print(f"        output: {json.dumps(shown, ensure_ascii=False)}")

    # Same message for "other company" and "unknown customer": the caller cannot tell them apart
    b = outputs.get("b_other_company_order.json", {}).get("message")
    c = outputs.get("c_unknown_customer.json", {}).get("message")
    same = b is not None and b == c
    failures += not same
    print(f"{'PASS' if same else 'FAIL'}  identical message for other-company and unknown-customer cases")

    print(f"\n{len(TESTS) + 1 - failures} passed, {failures} failed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
