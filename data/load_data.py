"""
Load the generated Delta Industrial Supplies data into the Salesforce org.

All calls go through the Salesforce CLI (see sf_cli.py), which holds the session
you created with `sf org login web`. No passwords or tokens are stored or handled.

Load order follows the data model's dependencies:
  Products -> Price book entries -> Accounts -> Contacts -> Orders
  -> Order products -> activate Orders -> Cases -> Opportunities

Run:  python data/load_data.py            (loads into the default org)
      python data/load_data.py --org delta-dev
"""

import argparse
import json
import sys
from pathlib import Path

from sf_cli import SalesforceCLI

DATA_DIR = Path(__file__).parent / "generated"


def load(name):
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def clean(record):
    """Drop helper keys (starting with _) and empty values before sending to Salesforce."""
    return {k: v for k, v in record.items() if not k.startswith("_") and v is not None}


def insert(sf, sobject, records):
    ids = sf.insert(sobject, records)
    print(f"  {sobject:<16} {len(ids):>4} inserted")
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="Org alias (default: the CLI default org)")
    args = parser.parse_args()

    sf = SalesforceCLI(args.org)

    # Safety check: do not load twice (duplicate customers would break the agent tests)
    existing = sf.query("SELECT Id FROM Account WHERE Customer_Number__c != null LIMIT 1")
    if existing:
        sys.exit("The org already contains Delta customers. Data was loaded before; nothing done.")

    products, accounts = load("products"), load("accounts")
    contacts, orders = load("contacts"), load("orders")
    cases, opps = load("cases"), load("opportunities")

    print("Loading data...")

    # 1. Products
    product_ids = insert(sf, "Product2", [clean(p) for p in products])
    product_by_code = {p["ProductCode"]: pid for p, pid in zip(products, product_ids)}

    # 2. Standard price book (must exist and be active for orders)
    pb = sf.query("SELECT Id, IsActive FROM Pricebook2 WHERE IsStandard = true")[0]
    if not pb["IsActive"]:
        sf.update("Pricebook2", [{"Id": pb["Id"], "IsActive": True}])
        print("  Activated the Standard Price Book")
    entry_ids = insert(sf, "PricebookEntry", [
        {"Pricebook2Id": pb["Id"], "Product2Id": product_by_code[p["ProductCode"]],
         "UnitPrice": p["_unit_price"], "IsActive": True}
        for p in products
    ])
    entry_by_code = {p["ProductCode"]: eid for p, eid in zip(products, entry_ids)}

    # 3. Accounts and contacts
    account_ids = insert(sf, "Account", [clean(a) for a in accounts])
    account_by_num = {a["Customer_Number__c"]: aid for a, aid in zip(accounts, account_ids)}
    insert(sf, "Contact", [{**clean(c), "AccountId": account_by_num[c["_account"]]} for c in contacts])

    # 4. Orders (created as Draft), then order products, then activate
    order_ids = insert(sf, "Order", [
        {**clean(o), "AccountId": account_by_num[o["_account"]], "Pricebook2Id": pb["Id"], "Status": "Draft"}
        for o in orders
    ])
    order_by_name = {o["Name"]: oid for o, oid in zip(orders, order_ids)}
    insert(sf, "OrderItem", [
        {"OrderId": order_by_name[o["Name"]], "PricebookEntryId": entry_by_code[i["ProductCode"]],
         "Quantity": i["Quantity"], "UnitPrice": i["UnitPrice"]}
        for o in orders for i in o["_items"]
    ])
    sf.update("Order", [{"Id": oid, "Status": "Activated"} for oid in order_ids])
    print(f"  Order activation  {len(order_ids)}/{len(order_ids)} activated")

    # 5. Cases and opportunities
    insert(sf, "Case", [
        {**clean(c), "AccountId": account_by_num[c["_account"]], "Related_Order__c": order_by_name[c["_order"]]}
        for c in cases
    ])
    insert(sf, "Opportunity", [{**clean(o), "AccountId": account_by_num[o["_account"]]} for o in opps])

    print("Done. Open the org and check Accounts, Orders and Products.")


if __name__ == "__main__":
    main()
