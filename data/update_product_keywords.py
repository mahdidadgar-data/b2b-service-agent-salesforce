"""
Update ONLY Product2.Search_Keywords__c on the products already in the org, from data/generated/products.json.

Why a separate script: load_data.py loads everything from scratch and refuses to run on an org that
already has data. This script changes one field on existing records and nothing else:
  - matches records on ProductCode (stops if a product is missing or appears twice in the org)
  - sends only Id + Search_Keywords__c (no other field can change)
  - dry run by default: shows what would change; --apply writes
  - after --apply, reads the values back from the org and checks every product

All calls go through the Salesforce CLI (data/sf_cli.py); no token is handled.

Run:  python data/update_product_keywords.py --org delta-dev            (dry run)
      python data/update_product_keywords.py --org delta-dev --apply    (update + verify)
Run data/preflight.py first. Exit code 0 = ok, 1 = problem.
"""

import argparse
import json
import sys
from pathlib import Path

from sf_cli import SalesforceCLI

PRODUCTS = Path(__file__).parent / "generated" / "products.json"
FIELD = "Search_Keywords__c"


def org_products(sf):
    rows = sf.query(f"SELECT Id, ProductCode, {FIELD} FROM Product2")
    by_code = {}
    for r in rows:
        by_code.setdefault(r["ProductCode"], []).append(r)
    return by_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="Org alias (default: the CLI default org)")
    parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run)")
    args = parser.parse_args()
    sf = SalesforceCLI(org=args.org)

    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    by_code = org_products(sf)

    problems = []
    updates = []
    for p in products:
        matches = by_code.get(p["ProductCode"], [])
        if len(matches) != 1:
            problems.append(f"{p['ProductCode']}: {len(matches)} records in the org (expected exactly 1)")
            continue
        if not p.get(FIELD):
            problems.append(f"{p['ProductCode']}: no {FIELD} in products.json")
            continue
        current = matches[0].get(FIELD)
        if current != p[FIELD]:
            updates.append({"Id": matches[0]["Id"], FIELD: p[FIELD], "_code": p["ProductCode"], "_old": current})
    if problems:
        print("Stopped, nothing written:")
        for line in problems:
            print(f"  {line}")
        sys.exit(1)

    print(f"{len(products)} products in products.json, all matched exactly once on ProductCode.")
    print(f"{len(updates)} product(s) need {FIELD}, {len(products) - len(updates)} already up to date.")
    for u in updates:
        print(f"  {u['_code']:<18} {str(u['_old'])!r:>6} -> {u[FIELD]!r}")

    if not args.apply:
        print("\nDry run: nothing written. Add --apply to update.")
        return
    if updates:
        sf.update("Product2", [{"Id": u["Id"], FIELD: u[FIELD]} for u in updates])
        print(f"\nUpdated {len(updates)} product(s) (only Id + {FIELD} sent).")

    # Verify: read every product back from the org and compare with products.json.
    by_code = org_products(sf)
    wrong = [p["ProductCode"] for p in products if by_code[p["ProductCode"]][0].get(FIELD) != p[FIELD]]
    filled = sum(1 for rows in by_code.values() for r in rows if r.get(FIELD))
    print(f"Verify: {filled} of {sum(len(v) for v in by_code.values())} products in the org have {FIELD}; "
          f"{len(products) - len(wrong)} of {len(products)} match products.json exactly.")
    if wrong:
        print(f"  mismatch: {wrong}")
        sys.exit(1)


if __name__ == "__main__":
    main()
