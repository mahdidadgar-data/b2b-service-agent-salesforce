"""
API tests for the agent actions (Flows): order status, complaints and product specs.

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
    g) unknown customer + order   -> no case, exactly the Get_Order_Status not-found message (no leak)
  Each test also counts the agent's cases in the org before and after the call, so it proves
  how many cases the call really created. This suite writes data: afterwards it deletes the
  cases it created (only those, by Id), even if a test failed.

Suite 3: Get_Product_Specs (UC2: product and spec questions; read-only, no cleanup needed)
  Request bodies:  tests/flows/get_product_specs/*.json
  Ground truth:    data/generated/products.json
    a) part of a code/name ("DP-200")       -> found, every spec field matches the data
    b) exact product code                   -> found
    c) "Ball Valve"                         -> several matches: names listed (max 10), no specs
    d) exact name, product without pressure -> found, maxPressureBar empty (never "0")
    e) unknown term                         -> not found
    f) "ab" (too short), g) blank           -> fail closed
    Word-based search: every word must appear in the name or code, in any order, case-insensitive.
    h) "DIS-"                               -> 29 matches, exactly 10 names listed (the cap)
    i) "ball valve DN25"                    -> 2 matches (brass and stainless DN25)
    j) "DN25 stainless ball valve"          -> found (words in another order)
    k) "dp-200 pump"                        -> found (lower case)
    l1-l3) "ball valve 50%", "ball_valve", "ball%dn25" -> not found: % and _ are literal, never wildcards
    Dutch terms via Product2.Search_Keywords__c (used for matching only):
    m) "kogelafsluiter DN25"   -> 2 matches,  n) "circulatiepomp DP-200" -> found,
    o) "leidingisolatie 13 mm" -> found,      p) "kogelkraan rvs DN25" -> Ball Valve Stainless DN25
    q) "diesel"                -> not found: only Delta's catalog is active (the Developer Edition
                                  sample products, e.g. GenWatt Diesel, are deactivated)
  Every test also checks that no keyword text (Search_Keywords__c) appears in any output value.
  Every test also checks that the flow returns no outputs beyond the declared spec fields
  (no prices, stock or other data).

Run:  python tests/run_flow_tests.py                      (default org, all suites)
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
    ("g", "g_unknown_customer_with_order.json", "g) C-9999 + SO-10447 -> not found, identical message", 0,
     check_not_found),
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


# =============================================================== Suite 3: Get_Product_Specs
GPS_DIR = FLOWS_DIR / "get_product_specs"
PRODUCTS = json.loads((ROOT / "data" / "generated" / "products.json").read_text(encoding="utf-8"))
PRODUCTS_BY_CODE = {p["ProductCode"]: p for p in PRODUCTS}
SPEC_FIELDS = ("productName", "productCode", "category", "maxPressureBar", "minTemperatureC", "maxTemperatureC",
               "connectionSize", "material", "datasheetText")
ALLOWED_OUTPUTS = set(SPEC_FIELDS) | {"productFound", "matchCount", "matchingProducts", "message"}
PRODUCT_NOT_FOUND = "I couldn't find a product matching that name or code. Please check it."
PRODUCT_MISSING_INPUT = "Please give me the product name or product code."
SEVERAL_PRODUCTS = "Several products match. Please tell me which one you mean."


def empty(value):
    return value in (None, "")


def number_text(value):
    """How the flow should show a number field: '10' for 10.0, '-10' for -10, empty for no value."""
    if value is None:
        return None
    return str(int(value)) if float(value).is_integer() else str(value)


def only_allowed_outputs(out):
    extra = sorted(k for k in out if not k.startswith("Flow__") and k not in ALLOWED_OUTPUTS)
    return (f"no outputs beyond the spec fields (extra: {extra})", not extra)


# Search_Keywords__c is used for matching only and must never leave the flow. only_allowed_outputs()
# proves there is no keyword OUTPUT; this proves no keyword TEXT reaches any output value either.
# Keyword-only terms are keyword terms that appear nowhere in the product data itself (name, code,
# datasheet, ...), e.g. "kogelafsluiter" or "pipe lagging": they can only come from Search_Keywords__c.
_PRODUCT_TEXT = " ".join(
    f"{p['Name']} {p['ProductCode']} {p['Category__c']} {p['Material__c']} {p['Connection_Size__c']} "
    f"{p['Datasheet_Text__c']} {p.get('Description') or ''}" for p in PRODUCTS).lower()
KEYWORD_ONLY_TERMS = sorted({t.strip().lower() for p in PRODUCTS for t in (p.get("Search_Keywords__c") or "").split(",")
                             if t.strip() and t.strip().lower() not in _PRODUCT_TEXT})


def keywords_not_returned(out):
    values = " ".join(str(v) for k, v in out.items() if not k.startswith("Flow__") and v is not None).lower()
    leaked = [t for t in KEYWORD_ONLY_TERMS if t in values]
    return (f"no Search_Keywords__c text in any output ({len(KEYWORD_ONLY_TERMS)} keyword-only terms checked; "
            f"leaked: {leaked})", not leaked)


def expect_product(code, extra_checks=()):
    """Exactly one product found; every spec output matches products.json."""
    p = PRODUCTS_BY_CODE[code]

    def check(out):
        same_number = lambda key, field: (empty(out.get(key)) if p[field] is None
                                          else out.get(key) == number_text(p[field]))
        checks = [
            ("productFound is true", out.get("productFound") is True),
            ("matchCount is 1", out.get("matchCount") == 1),
            ("productName matches data", out.get("productName") == p["Name"]),
            ("productCode matches data", out.get("productCode") == p["ProductCode"]),
            ("category matches data", out.get("category") == p["Category__c"]),
            ("maxPressureBar matches data", same_number("maxPressureBar", "Max_Pressure_bar__c")),
            ("minTemperatureC matches data", same_number("minTemperatureC", "Min_Temperature_C__c")),
            ("maxTemperatureC matches data", same_number("maxTemperatureC", "Max_Temperature_C__c")),
            ("connectionSize matches data", out.get("connectionSize") == p["Connection_Size__c"]),
            ("material matches data", out.get("material") == p["Material__c"]),
            ("datasheetText matches data", out.get("datasheetText") == p["Datasheet_Text__c"]),
            ("message is empty", empty(out.get("message"))),
            ("matchingProducts is empty", empty(out.get("matchingProducts"))),
            only_allowed_outputs(out),
            keywords_not_returned(out),
        ]
        return checks + [(name, fn(out)) for name, fn in extra_checks]
    return check


def expect_no_product(message, match_count=0):
    def check(out):
        checks = [
            ("productFound is false", out.get("productFound") is False),
            (f"message is '{message}'", out.get("message") == message),
            (f"matchCount is {match_count}", out.get("matchCount") == match_count),
            ("matchingProducts is empty", empty(out.get("matchingProducts"))),
            only_allowed_outputs(out),
            keywords_not_returned(out),
        ]
        return checks + [(f"{f} not returned", empty(out.get(f))) for f in SPEC_FIELDS]
    return check


def word_matches(term):
    """The flow's matching rule, computed on products.json: every word (split on spaces) appears in the
    name, product code or search keywords, case-insensitive, literal text, any order. Active products only."""
    words = [w.lower() for w in term.strip().split(" ") if w]
    return sorted(p["Name"] for p in PRODUCTS
                  if p["IsActive"] and all(
                      w in f"{p['Name']} {p['ProductCode']} {p.get('Search_Keywords__c') or ''}".lower()
                      for w in words))


def listed_names(out):
    return [n for n in (out.get("matchingProducts") or "").split("; ") if n]


def expect_several(term, extra_checks=()):
    expected = word_matches(term)

    def check(out):
        names = listed_names(out)
        checks = [
            ("productFound is false", out.get("productFound") is False),
            (f"matchCount is {len(expected)} (> 1, from products.json)",
             out.get("matchCount") == len(expected) and len(expected) > 1),
            ("at most 10 names listed", 0 < len(names) <= 10),
            ("listed names are real matches", set(names) <= set(expected)),
            ("all matches listed when there are 10 or fewer", len(expected) > 10 or set(names) == set(expected)),
            ("several-matches message", out.get("message") == SEVERAL_PRODUCTS),
            only_allowed_outputs(out),
            keywords_not_returned(out),
        ]
        checks += [(f"{f} not returned", empty(out.get(f))) for f in SPEC_FIELDS]
        return checks + [(name, fn(out)) for name, fn in extra_checks]
    return check


GPS_TESTS = [
    ("a_code_part.json", "a) 'DP-200' (part of a code/name) -> Circulation Pump DP-200",
     expect_product("DIS-PMP-DP-200", [("maxPressureBar is '10'", lambda o: o.get("maxPressureBar") == "10")])),
    ("b_full_code.json", "b) 'DIS-VLV-BS-DN25' (exact code) -> Ball Valve Stainless DN25",
     expect_product("DIS-VLV-BS-DN25", [("material is 'Stainless steel AISI 316'",
                                         lambda o: o.get("material") == "Stainless steel AISI 316")])),
    ("c_ambiguous.json", "c) 'Ball Valve' -> several matches, customer must choose",
     expect_several("Ball Valve", [("list contains a brass and a stainless valve",
                                    lambda o: any("Brass" in n for n in listed_names(o))
                                    and any("Stainless" in n for n in listed_names(o)))])),
    ("d_no_pressure.json", "d) 'Pipe Insulation Flexible 13 mm' (exact name) -> found, no pressure",
     expect_product("DIS-INS-FL-13", [("maxPressureBar is empty, not '0'",
                                       lambda o: empty(o.get("maxPressureBar")) and o.get("maxPressureBar") != "0")])),
    ("e_unknown.json", "e) 'XYZ-999' -> not found", expect_no_product(PRODUCT_NOT_FOUND)),
    ("f_too_short.json", "f) 'ab' (too short) -> fail closed", expect_no_product(PRODUCT_MISSING_INPUT)),
    ("g_blank.json", "g) blank -> fail closed", expect_no_product(PRODUCT_MISSING_INPUT)),
    # Word-based search (words in any order, every word must appear in the name or code)
    ("h_cap_ten_names.json", "h) 'DIS-' -> 29 matches, exactly 10 names listed (cap)",
     expect_several("DIS-", [("matchCount is 29", lambda o: o.get("matchCount") == 29),
                             ("exactly 10 names listed", lambda o: len(listed_names(o)) == 10)])),
    ("i_words_two_matches.json", "i) 'ball valve DN25' -> brass + stainless DN25",
     expect_several("ball valve DN25", [("matchCount is 2", lambda o: o.get("matchCount") == 2),
                                        ("both DN25 ball valves listed",
                                         lambda o: set(listed_names(o)) == {"Ball Valve Brass DN25",
                                                                            "Ball Valve Stainless DN25"})])),
    ("j_words_any_order.json", "j) 'DN25 stainless ball valve' -> Ball Valve Stainless DN25",
     expect_product("DIS-VLV-BS-DN25")),
    ("k_words_lowercase.json", "k) 'dp-200 pump' -> Circulation Pump DP-200", expect_product("DIS-PMP-DP-200")),
    # % and _ must be literal characters, never wildcards
    ("l1_percent_literal.json", "l1) 'ball valve 50%' -> not found (% literal, checked in the flow)",
     expect_no_product(PRODUCT_NOT_FOUND)),
    ("l2_underscore_literal.json", "l2) 'ball_valve' -> not found (_ literal, also in the database pre-filter)",
     expect_no_product(PRODUCT_NOT_FOUND)),
    ("l3_percent_in_prefilter.json", "l3) 'ball%dn25' -> not found (% literal, also in the database pre-filter)",
     expect_no_product(PRODUCT_NOT_FOUND)),
    # Dutch search terms through Search_Keywords__c (matching only, never returned)
    ("m_dutch_two_matches.json", "m) 'kogelafsluiter DN25' -> brass + stainless DN25",
     expect_several("kogelafsluiter DN25", [("matchCount is 2", lambda o: o.get("matchCount") == 2),
                                            ("both DN25 ball valves listed",
                                             lambda o: set(listed_names(o)) == {"Ball Valve Brass DN25",
                                                                                "Ball Valve Stainless DN25"})])),
    ("n_dutch_pump.json", "n) 'circulatiepomp DP-200' -> Circulation Pump DP-200", expect_product("DIS-PMP-DP-200")),
    ("o_dutch_insulation.json", "o) 'leidingisolatie 13 mm' -> Pipe Insulation Flexible 13 mm",
     expect_product("DIS-INS-FL-13")),
    ("p_dutch_rvs.json", "p) 'kogelkraan rvs DN25' -> Ball Valve Stainless DN25 ('rvs' = stainless)",
     expect_product("DIS-VLV-BS-DN25", [("maxPressureBar is '40'", lambda o: o.get("maxPressureBar") == "40")])),
    # Only Delta's own catalog is searchable: the Developer Edition sample products are inactive
    ("q_sample_product_inactive.json", "q) 'diesel' -> not found (sample products are inactive)",
     expect_no_product(PRODUCT_NOT_FOUND)),
]


def run_get_product_specs(org_args, sf):
    """Read-only flow: no data is created, so no cleanup. Returns (number of checks run, number failed)."""
    failures = 0
    for filename, title, expectations in GPS_TESTS:
        try:
            out = call_flow("Get_Product_Specs", GPS_DIR / filename, org_args)
            checks = expectations(out)
        except Exception as exc:  # noqa: BLE001  (report and count as a failure)
            out, checks = {}, [(f"call succeeded ({exc})", False)]
        if "datasheetText" in out and out["datasheetText"]:
            out = {**out, "datasheetText": out["datasheetText"][:60] + "…"}  # keep the printed output short
        failures += report(title, out, checks)
    return len(GPS_TESTS), failures


SUITES = {
    "get_order_status": ("Get_Order_Status", run_get_order_status),
    "create_complaint_case": ("Create_Complaint_Case", run_create_complaint_case),
    "get_product_specs": ("Get_Product_Specs", run_get_product_specs),
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
