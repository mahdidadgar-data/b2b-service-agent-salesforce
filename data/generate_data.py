"""
Generate synthetic B2B data for Delta Industrial Supplies (fictional).

Pure Python, no Salesforce connection: produces JSON files in data/generated/
that load_data.py then loads into the org. Keeping generation separate from
loading means the data is reviewable, version-controlled and reproducible
(fixed random seed), and the same files can later be used as ground truth
for the evaluation set.

Run:  python data/generate_data.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
TODAY = date.today()
OUT_DIR = Path(__file__).parent / "generated"

random.seed(SEED)


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
def make_products():
    products = []

    def add(code, name, category, price, pressure, tmin, tmax, size, material, application, notes):
        sheet = (
            f"{name} ({code})\n"
            f"Category: {category}\n"
            f"Application: {application}\n"
            f"Connection size: {size}\n"
            f"Material: {material}\n"
            + (f"Maximum operating pressure: {pressure} bar\n" if pressure is not None else
               "Maximum operating pressure: not applicable\n")
            + f"Operating temperature range: {tmin} °C to {tmax} °C\n"
            f"Notes: {notes}\n"
            "Installation must be carried out by a qualified installer in line with local regulations. "
            "Delta Industrial Supplies does not give installation or design advice beyond this datasheet."
        )
        products.append({
            "ProductCode": code,
            "Name": name,
            "Category__c": category,
            "Max_Pressure_bar__c": pressure,
            "Min_Temperature_C__c": tmin,
            "Max_Temperature_C__c": tmax,
            "Connection_Size__c": size,
            "Material__c": material,
            "Datasheet_Text__c": sheet,
            "Description": application,
            "IsActive": True,
            "_unit_price": price,
        })

    # Pumps
    for model, pressure, tmax, size, price in [
        ("DP-100", 6.0, 95, "DN25 / 1 inch", 289.00),
        ("DP-200", 10.0, 110, "DN32 / 1 1/4 inch", 465.00),
        ("DP-300", 16.0, 120, "DN40 / 1 1/2 inch", 812.00),
    ]:
        add(f"DIS-PMP-{model}", f"Circulation Pump {model}", "Pumps", price, pressure, -10, tmax, size,
            "Cast iron housing, stainless steel impeller",
            "Circulation of heating and chilled water in commercial buildings.",
            "Not suitable for drinking water or seawater. Variable-speed EC motor, 230 V.")
    for model, pressure, size, price in [
        ("SP-40", 4.0, "DN40 / 1 1/2 inch", 349.00),
        ("SP-50", 6.0, "DN50 / 2 inch", 529.00),
    ]:
        add(f"DIS-PMP-{model}", f"Submersible Drainage Pump {model}", "Pumps", price, pressure, 0, 40, size,
            "Stainless steel AISI 304",
            "Drainage of clean and lightly contaminated water from pits and basements.",
            "Maximum solids size 10 mm. Not for flammable liquids.")

    # Valves
    for dn, inch, price_brass, price_ss in [
        ("DN15", "1/2 inch", 12.40, 31.90), ("DN20", "3/4 inch", 15.80, 39.50),
        ("DN25", "1 inch", 21.30, 52.00), ("DN32", "1 1/4 inch", 34.90, 78.40),
        ("DN50", "2 inch", 68.00, 149.00),
    ]:
        add(f"DIS-VLV-BB-{dn}", f"Ball Valve Brass {dn}", "Valves", price_brass, 25.0, -20, 120,
            f"{dn} / {inch}", "Nickel-plated brass (CW617N)",
            "Shut-off for heating, cooling and compressed air installations.",
            "Full bore. Not approved for gas installations.")
        add(f"DIS-VLV-BS-{dn}", f"Ball Valve Stainless {dn}", "Valves", price_ss, 40.0, -30, 180,
            f"{dn} / {inch}", "Stainless steel AISI 316",
            "Shut-off for process water, chemicals (check compatibility) and steam up to 180 °C.",
            "Full bore. Seals PTFE.")
    for dn, price in [("DN25", 44.50), ("DN50", 96.00)]:
        add(f"DIS-VLV-CK-{dn}", f"Check Valve {dn}", "Valves", price, 16.0, -10, 100,
            dn, "Brass body, stainless steel spring",
            "Prevents backflow in pumped water systems.",
            "Install in the direction of the arrow on the body.")

    # Fittings
    for size, price in [("15 mm", 1.85), ("22 mm", 2.60), ("28 mm", 3.95)]:
        add(f"DIS-FIT-PE-{size.split()[0]}", f"Press Fitting Elbow 90° {size}", "Fittings", price, 16.0, -20, 110,
            size, "Copper with EPDM O-ring",
            "Press connection for copper pipe in heating and drinking water.",
            "Use the matching press profile (V-profile).")
    for dn, price in [("DN25", 6.20), ("DN50", 14.80)]:
        add(f"DIS-FIT-TS-{dn}", f"Threaded Tee Stainless {dn}", "Fittings", price, 25.0, -30, 200,
            dn, "Stainless steel AISI 316",
            "Branch connection in process and industrial piping.",
            "BSP thread. Use suitable thread sealant.")

    # Insulation (no pressure rating)
    for thickness, price in [("13 mm", 4.10), ("19 mm", 5.75), ("25 mm", 7.90)]:
        add(f"DIS-INS-FL-{thickness.split()[0]}", f"Pipe Insulation Flexible {thickness}", "Insulation", price,
            # Connection_Size__c is Text(30): keep the size summary short
            None, -50, 105, f"{thickness} wall, pipe 15-54 mm", "Closed-cell elastomeric foam",
            "Thermal insulation and condensation control for heating and cooling pipes. Sold per 2 m length.",
            "Fire class BL-s3,d0. Not for outdoor use without UV protection.")
    add("DIS-INS-MW-50", "Mineral Wool Pipe Section 50 mm", "Insulation", 18.40,
        None, 0, 250, "50 mm wall, pipe up to 114 mm", "Mineral wool with aluminium foil",
        "High-temperature insulation for steam and hot process pipes. Sold per 1 m length.",
        "Fire class A2L-s1,d0. Wear gloves and a dust mask when cutting.")

    # Fixings
    for size, price in [("15-19 mm", 1.10), ("26-30 mm", 1.45), ("48-53 mm", 2.30)]:
        add(f"DIS-FIX-PC-{size.split('-')[0]}", f"Pipe Clamp with Rubber Lining {size}", "Fixings", price,
            None, -20, 100, size, "Galvanised steel, EPDM lining",
            "Fixing pipes to walls and ceilings with noise and vibration damping.",
            "Includes M8/M10 combination nut.")

    return products


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------
ACCOUNTS = [
    ("C-1001", "Van der Berg Installatietechniek B.V.", "Installer", "Utrecht", "NL"),
    ("C-1002", "Bouwbedrijf Hoekstra B.V.", "Contractor", "Zwolle", "NL"),
    ("C-1003", "Klimaatwerk Rotterdam B.V.", "Installer", "Rotterdam", "NL"),
    ("C-1004", "FMS Facility Services Nederland", "Facility Management", "Amersfoort", "NL"),
    ("C-1005", "Peeters Technieken BV", "Installer", "Antwerpen", "BE"),
    ("C-1006", "Noordzee Procesindustrie B.V.", "Industrial", "Delfzijl", "NL"),
    ("C-1007", "De Wit & Zonen Loodgieters", "Installer", "Eindhoven", "NL"),
    ("C-1008", "Bouwcombinatie A12 V.O.F.", "Contractor", "Arnhem", "NL"),
    ("C-1009", "Maes Facility Group NV", "Facility Management", "Gent", "BE"),
    ("C-1010", "Brabant Food Processing B.V.", "Industrial", "Tilburg", "NL"),
    ("C-1011", "Jansen Duurzame Installaties", "Installer", "Haarlem", "NL"),
    ("C-1012", "Smit Utiliteitsbouw B.V.", "Contractor", "Leeuwarden", "NL"),
]

FIRST = ["Sanne", "Daan", "Lotte", "Bram", "Eva", "Tim", "Noor", "Jeroen", "Fleur", "Ruben", "Lies", "Koen"]
LAST = ["de Jong", "Bakker", "Visser", "Smit", "Meijer", "Mulder", "Bos", "Vos", "Peters", "Hendriks",
        "Dekker", "Brouwer"]
TITLES = ["Purchasing Manager", "Project Leader", "Service Coordinator", "Site Manager", "Buyer"]


def slug(text):
    return "".join(c for c in text.lower() if c.isalnum())[:18]


def make_accounts_and_contacts():
    accounts, contacts = [], []
    for i, (num, name, segment, city, country) in enumerate(ACCOUNTS):
        accounts.append({
            "Customer_Number__c": num,
            "Name": name,
            "Customer_Segment__c": segment,
            "Type": "Customer - Direct",  # a standard Account.Type picklist value
            "Industry": "Construction" if segment in ("Installer", "Contractor") else "Manufacturing",
            "BillingCity": city,
            "BillingCountry": "Netherlands" if country == "NL" else "Belgium",
        })
        for j in range(2 if i % 3 == 0 else 1):
            first = FIRST[(i + j * 5) % len(FIRST)]
            last = LAST[(i * 2 + j) % len(LAST)]
            contacts.append({
                "_account": num,
                "FirstName": first,
                "LastName": last,
                "Title": TITLES[(i + j) % len(TITLES)],
                # .example is a reserved domain: these addresses can never reach a real person
                "Email": f"{first.lower()}.{slug(last)}@{slug(name)}.example",
            })
    return accounts, contacts


# --------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------
CARRIERS = ["PostNL Pakketten", "DHL Freight", "DB Schenker", "Delta own truck"]
DELAY_REASONS = [
    "Supplier delivered later than planned; new stock expected this week.",
    "Partial stock shortage on one item; order will ship complete.",
    "Carrier capacity problem in the region.",
]


def make_orders(products, accounts):
    orders = []
    order_no = 10440
    status_plan = (["Delivered"] * 14 + ["Shipped"] * 8 + ["In Preparation"] * 7 +
                   ["Received"] * 6 + ["Delayed"] * 5)
    random.shuffle(status_plan)
    for k, status in enumerate(status_plan):
        account = accounts[k % len(accounts)]
        order_no += random.randint(1, 4)
        if status == "Delivered":
            ordered = TODAY - timedelta(days=random.randint(12, 60))
            expected = ordered + timedelta(days=random.randint(2, 6))
        elif status == "Shipped":
            ordered = TODAY - timedelta(days=random.randint(2, 6))
            expected = TODAY + timedelta(days=random.randint(0, 2))
        elif status == "In Preparation":
            ordered = TODAY - timedelta(days=random.randint(0, 3))
            expected = TODAY + timedelta(days=random.randint(2, 5))
        elif status == "Received":
            ordered = TODAY - timedelta(days=random.randint(0, 1))
            expected = TODAY + timedelta(days=random.randint(3, 8))
        else:  # Delayed
            ordered = TODAY - timedelta(days=random.randint(6, 14))
            expected = TODAY + timedelta(days=random.randint(2, 7))

        has_tracking = status in ("Shipped", "Delivered")
        carrier = random.choice(CARRIERS) if has_tracking else None
        items = []
        for p in random.sample(products, random.randint(1, 4)):
            qty = random.choice([1, 2, 4, 5, 10, 20, 25, 50]) if p["Category__c"] in ("Fittings", "Fixings", "Insulation") \
                else random.choice([1, 2, 3, 4, 6, 10])
            items.append({"ProductCode": p["ProductCode"], "Quantity": qty, "UnitPrice": p["_unit_price"]})

        orders.append({
            "Name": f"SO-{order_no}",
            "_account": account["Customer_Number__c"],
            "EffectiveDate": ordered.isoformat(),
            "PoNumber": f"PO-{random.randint(2000, 9999)}",
            "Delivery_Status__c": status,
            "Expected_Delivery_Date__c": expected.isoformat(),
            "Carrier__c": carrier,
            "Tracking_Number__c": (f"3S{random.randint(10**9, 10**10 - 1)}" if carrier == "PostNL Pakketten"
                                   else f"{random.randint(10**9, 10**10 - 1)}") if has_tracking and carrier != "Delta own truck" else None,
            "Delay_Reason__c": random.choice(DELAY_REASONS) if status == "Delayed" else None,
            "_items": items,
        })
    return orders


# --------------------------------------------------------------------------
# Existing cases and quote requests (history the agent may encounter)
# --------------------------------------------------------------------------
def make_cases(orders):
    delivered = [o for o in orders if o["Delivery_Status__c"] == "Delivered"]
    templates = [
        ("Damaged goods: cracked fittings", "Three press fittings arrived cracked. Photos available.", "High"),
        ("Wrong item delivered", "We received DN20 ball valves instead of DN25.", "Medium"),
        ("Missing item in delivery", "Delivery was complete except for the pipe clamps.", "Medium"),
        ("Return request: excess quantity", "Ordered too much insulation, want to return 10 lengths unopened.", "Low"),
    ]
    cases = []
    for (subject, desc, prio), order in zip(templates, delivered):
        cases.append({
            "_order": order["Name"], "_account": order["_account"],
            "Subject": subject, "Description": desc, "Priority": prio,
            "Status": "New", "Origin": "Email", "Created_By_Agent__c": "Human",
        })
    return cases


def make_opportunities(accounts):
    requests = [
        ("C-1002", "Quote: ball valves for school renovation Zwolle", "40x Ball Valve Brass DN25, 10x Ball Valve Brass DN50", "Zwolle, Campus Noord", 21),
        ("C-1006", "Quote: stainless valves for process line 3", "12x Ball Valve Stainless DN50, 12x Threaded Tee Stainless DN50", "Delfzijl, Plant 2", 35),
        ("C-1008", "Quote: pumps for apartment block A12-West", "6x Circulation Pump DP-200", "Arnhem, A12-West", 45),
    ]
    opps = []
    for num, name, items, location, days in requests:
        opps.append({
            "_account": num, "Name": name, "StageName": "Prospecting",
            "CloseDate": (TODAY + timedelta(days=days)).isoformat(),
            "Requested_Items__c": items, "Delivery_Location__c": location,
            "Requested_Delivery_Date__c": (TODAY + timedelta(days=days + 14)).isoformat(),
            "LeadSource": "Web",
        })
    return opps


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    products = make_products()
    accounts, contacts = make_accounts_and_contacts()
    orders = make_orders(products, accounts)
    data = {
        "products": products,
        "accounts": accounts,
        "contacts": contacts,
        "orders": orders,
        "cases": make_cases(orders),
        "opportunities": make_opportunities(accounts),
    }
    for name, rows in data.items():
        (OUT_DIR / f"{name}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{name:<14} {len(rows):>4} records")
    print(f"Order items    {sum(len(o['_items']) for o in orders):>4} records")
    print(f"Written to {OUT_DIR}")


if __name__ == "__main__":
    main()
