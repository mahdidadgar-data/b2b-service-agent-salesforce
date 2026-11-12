"""
API tests for the agent actions (Flows).

Calls each flow the same way an agent or integration does: through the REST invocable-action
endpoint (/actions/custom/flow/<FlowName>). Every call goes through the Salesforce CLI
(`sf api request rest`, or data/sf_cli.py for queries), so no token is handled here.

Suite 1: Get_Order_Status (UC1: order status)
  Request bodies:  tests/flows/get_order_status/*.json
  Ground truth:    data/generated/orders.json (the data that was loaded into the org)
    a) own order             -> found, with the status, date and delay reason from the data
    b) other company's order -> not found (guardrail: account filter)
    c) unknown customer      -> not found, with exactly the same message as b)
    d) empty customer number -> not found (guardrail must not depend on the input being filled)
  For every "not found" case, no order details may be returned (no information leak).

Suite 2: Create_Complaint_Case (UC4: complaint -> Case)
  Request bodies:  tests/flows/create_complaint_case/*.json
    a) own customer + own order   -> case created, every field checked in the org
    b) the same call again        -> no new case, the existing case number (duplicate protection)
    c) other company's order      -> no case, the standard not-found message (no information leak)
    d) customer only, no order    -> case created on the account, not linked to an order
    e) blank complaint            -> no case, the missing-input message
    f) unknown customer, no order -> no case, the customer-not-found message
  Each test also counts the agent's cases in the org before and after the call, so it proves
  how many cases the call really created. This suite writes data: afterwards it deletes the
  cases it created (only those, by Id), even if a test failed.

Run:  python tests/run_flow_tests.py                      (default org, both suites)
      python tests/run_flow_tests.py --org delta-dev
      python tests/run_flow_tests.py --suite get_order_status
Exit code 0 = all tests passed, 1 = at least one failure.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data"))
from sf_cli import SalesforceCLI  # noqa: E402  (shared CLI-based client)

FLOWS_DIR = ROOT / "tests" / "flows"
ORDERS = {o["Name"]: o for o in json.loads((ROOT / "data" / "generated" / "orders.json").read_text(encoding="utf-8"))}
API = "v62.0"
SF = shutil.which("sf") or "sf"

NOT_FOUND = "No order found for this customer number and order number. Please check both numbers."


def call_flow(flow, body_file, org_args):
    """POST one request body to the flow's invocable action; return the outputValues of the first result."""
    endpoint = f"/services/data/{API}/actions/custom/flow/{flow}"
    result = subprocess.run([SF, "api", "request", "rest", endpoint, "--method", "POST",
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


def report(title, out, checks):
    """Print one test result. Returns 1 if any check failed, else 0."""
    failed = [name for name, ok in checks if not ok]
    print(f"{'PASS' if not failed else 'FAIL'}  {title}")
    for name in failed:
        print(f"        failed: {name}")
    shown = {k: v for k, v in out.items() if not k.startswith("Flow__")}
    print(f"        output: {json.dumps(shown, ensure_ascii=False)}")
    return int(bool(failed))


# ================================================================ Suite 1: Get_Order_Status
GOS_DIR = FLOWS_DIR / "get_order_status"
DETAIL_FIELDS = ("deliveryStatus", "expectedDeliveryDate", "carrier", "trackingNumber", "delayReason")


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


GOS_TESTS = [
    ("a_own_order.json", "C-1004 + SO-10447: own order", lambda o: expect_found(o, "SO-10447")),
    ("b_other_company_order.json", "C-1001 + SO-10447: other company's order", expect_not_found),
    ("c_unknown_customer.json", "C-9999 + SO-10447: unknown customer", expect_not_found),
    ("d_empty_customer.json", "empty customer + SO-10447", expect_not_found),
]


def run_get_order_status(org_args, sf):
    """Returns (number of checks run, number failed)."""
    failures = 0
    outputs = {}
    for filename, title, expectations in GOS_TESTS:
        try:
            out = call_flow("Get_Order_Status", GOS_DIR / filename, org_args)
            checks = expectations(out)
        except Exception as exc:  # noqa: BLE001  (report and count as a failure)
            out, checks = {}, [(f"call succeeded ({exc})", False)]
        outputs[filename] = out
        failures += report(title, out, checks)

    # Same message for "other company" and "unknown customer": the caller cannot tell them apart
    b = outputs.get("b_other_company_order.json", {}).get("message")
    c = outputs.get("c_unknown_customer.json", {}).get("message")
    same = b is not None and b == c
    failures += not same
    print(f"{'PASS' if same else 'FAIL'}  identical message for other-company and unknown-customer cases")
    return len(GOS_TESTS) + 1, failures


# =========================================================== Suite 2: Create_Complaint_Case
CCC_DIR = FLOWS_DIR / "create_complaint_case"
MISSING_INPUT = "I need your customer number and a short description of the problem to register a complaint."
CUSTOMER_NOT_FOUND = "I couldn't find a customer with this customer number. Please check it."
AGENT_CASES = "SELECT Id FROM Case WHERE Created_By_Agent__c = 'Agentforce'"
CASE_FIELDS = ("Id, CaseNumber, Account.Customer_Number__c, Related_Order__r.Name, Subject, Description, "
               "Origin, Status, Priority, Created_By_Agent__c")


def soql_ids(ids):
    return ", ".join(f"'{i}'" for i in ids)


def check_created(out, inputs, new_ids, sf, ctx, test_id):
    cn = out.get("caseNumber")
    ctx[test_id] = cn
    checks = [
        ("caseCreated is true", out.get("caseCreated") is True),
        ("caseNumber filled", bool(cn)),
        ("success message", out.get("message") ==
         f"Your complaint has been registered as case {cn}. A colleague will contact you."),
    ]
    if len(new_ids) != 1:
        return checks
    case = sf.query(f"SELECT {CASE_FIELDS} FROM Case WHERE Id = '{new_ids[0]}'")[0]
    order = inputs.get("orderNumber")
    expected_subject = "Complaint via service agent" + (f" - {order}" if order else "")
    checks += [
        ("case in org has the returned CaseNumber", case["CaseNumber"] == cn),
        ("case is on the customer's account",
         (case.get("Account") or {}).get("Customer_Number__c") == inputs["customerNumber"]),
        ("case linked to the right order (or none)",
         (case.get("Related_Order__r") or {}).get("Name") == order),
        (f"Subject is '{expected_subject}'", case["Subject"] == expected_subject),
        ("Description is the complaint", case["Description"] == inputs["complaintSummary"]),
        ("Origin = Web", case["Origin"] == "Web"),
        ("Status = New", case["Status"] == "New"),
        ("Priority = Medium", case["Priority"] == "Medium"),
        ("Created_By_Agent__c = Agentforce", case["Created_By_Agent__c"] == "Agentforce"),
    ]
    return checks


def check_duplicate(out, inputs, new_ids, sf, ctx, test_id):
    first = ctx.get("a")
    return [
        ("caseCreated is false", out.get("caseCreated") is False),
        ("caseNumber is the case from test a", first is not None and out.get("caseNumber") == first),
        ("duplicate message", out.get("message") ==
         f"There is already an open complaint for this order: {first}. A colleague will contact you."),
    ]


def check_not_found(out, inputs, new_ids, sf, ctx, test_id):
    return [
        ("caseCreated is false", out.get("caseCreated") is False),
        ("standard not-found message (identical to Get_Order_Status)", out.get("message") == NOT_FOUND),
        ("no caseNumber returned", out.get("caseNumber") is None),
    ]


def check_missing_input(out, inputs, new_ids, sf, ctx, test_id):
    return [
        ("caseCreated is false", out.get("caseCreated") is False),
        ("missing-input message", out.get("message") == MISSING_INPUT),
        ("no caseNumber returned", out.get("caseNumber") is None),
    ]


def check_customer_not_found(out, inputs, new_ids, sf, ctx, test_id):
    return [
        ("caseCreated is false", out.get("caseCreated") is False),
        ("customer-not-found message", out.get("message") == CUSTOMER_NOT_FOUND),
        ("no caseNumber returned", out.get("caseNumber") is None),
    ]


# (id, request body, title, expected number of new cases, checks). Order matters: b repeats a.
CCC_TESTS = [
    ("a", "a_own_order.json", "a) C-1004 + SO-10447: own order -> case created", 1, check_created),
    ("b", "a_own_order.json", "b) same call again -> duplicate protection", 0, check_duplicate),
    ("c", "c_other_company_order.json", "c) C-1001 + SO-10447: other company's order -> not found", 0,
     check_not_found),
    ("d", "d_customer_only.json", "d) C-1004, no order number -> case on the account", 1, check_created),
    ("e", "e_blank_summary.json", "e) blank complaint (whitespace only) -> refused", 0, check_missing_input),
    ("f", "f_unknown_customer_no_order.json", "f) C-9999, no order number -> customer not found", 0,
     check_customer_not_found),
]


def delete_cases(ids, org_args, sf):
    """Delete exactly these Case Ids. Returns the number confirmed deleted."""
    for case_id in ids:
        result = subprocess.run([SF, "data", "delete", "record", "--sobject", "Case", "--record-id", case_id,
                                 *org_args], capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            print(f"        could not delete {case_id}: {(result.stdout + result.stderr).strip()[:300]}")
    remaining = {r["Id"] for r in sf.query(f"SELECT Id FROM Case WHERE Id IN ({soql_ids(ids)})")} if ids else set()
    return len(ids) - len(remaining)


def run_create_complaint_case(org_args, sf):
    """Returns (number of checks run, number failed)."""
    # Precondition: an open agent case on SO-10447 left over from elsewhere would make test a a duplicate.
    # It is not ours, so we never delete it; we stop instead.
    leftover = sf.query("SELECT CaseNumber FROM Case WHERE Created_By_Agent__c = 'Agentforce' "
                        "AND IsClosed = false AND Related_Order__r.Name = 'SO-10447'")
    if leftover:
        print(f"FAIL  precondition: open agent case(s) on SO-10447 already exist: "
              f"{[r['CaseNumber'] for r in leftover]}. Close or delete them first.")
        return 1, 1

    failures = 0
    created = []  # Ids of every case this run created
    ctx = {}
    try:
        for test_id, filename, title, expected_new, checks_for in CCC_TESTS:
            inputs = json.loads((CCC_DIR / filename).read_text(encoding="utf-8"))["inputs"][0]
            before = {r["Id"] for r in sf.query(AGENT_CASES)}
            try:
                out = call_flow("Create_Complaint_Case", CCC_DIR / filename, org_args)
                call_error = None
            except Exception as exc:  # noqa: BLE001  (report and count as a failure)
                out, call_error = {}, exc
            new_ids = sorted({r["Id"] for r in sf.query(AGENT_CASES)} - before)
            created += new_ids
            if call_error:
                checks = [(f"call succeeded ({call_error})", False)]
            else:
                checks = [(f"{expected_new} new case(s) in the org (found {len(new_ids)})",
                           len(new_ids) == expected_new)]
                checks += checks_for(out, inputs, new_ids, sf, ctx, test_id)
            failures += report(title, out, checks)
    finally:
        deleted = delete_cases(created, org_args, sf)
        ok = deleted == len(created)
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  cleanup: deleted {deleted} of {len(created)} case(s) created by this run "
              f"{created}")
    return len(CCC_TESTS) + 1, failures


SUITES = {
    "get_order_status": ("Get_Order_Status", run_get_order_status),
    "create_complaint_case": ("Create_Complaint_Case", run_create_complaint_case),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="Org alias (default: the CLI default org)")
    parser.add_argument("--suite", choices=["all", *SUITES], default="all")
    args = parser.parse_args()
    org_args = ["--target-org", args.org] if args.org else []
    sf = SalesforceCLI(org=args.org)

    total = failures = 0
    for key, (flow, run) in SUITES.items():
        if args.suite not in ("all", key):
            continue
        print(f"\n=== {flow} ===")
        n, f = run(org_args, sf)
        total += n
        failures += f

    print(f"\n{total - failures} passed, {failures} failed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
