"""
Diagnose the connection between Python and the Salesforce org.
Prints facts about the session WITHOUT revealing the token itself.

Run:  python data/check_connection.py
"""

import json
import subprocess

import requests


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"status": "not-json", "raw": (r.stdout + r.stderr)[:300]}


print("1) Does the CLI itself reach the org (REST query through the CLI)?")
q = run('sf data query --query "SELECT COUNT() FROM Account" --json')
print("   CLI status:", q.get("status"), "| totalSize:", q.get("result", {}).get("totalSize"),
      "| message:", q.get("message"))

print("\n2) What does the CLI hand over?")
d = run("sf org display --verbose --json").get("result", {})
token = d.get("accessToken", "")
print("   username     :", d.get("username"))
print("   instanceUrl  :", d.get("instanceUrl"))
print("   apiVersion   :", d.get("apiVersion"))
print("   connected    :", d.get("connectedStatus"))
print("   token length :", len(token))
print("   has '!'      :", "!" in token, "| has spaces/newlines:", any(c.isspace() for c in token))
print("   other keys   :", sorted(k for k in d.keys() if k not in ("accessToken", "sfdxAuthUrl")))

base = d.get("instanceUrl", "")
ver = d.get("apiVersion") or "62.0"
for label, header in [("Bearer", f"Bearer {token}"), ("OAuth", f"OAuth {token}")]:
    for v in [ver, "59.0"]:
        url = f"{base}/services/data/v{v}/query/?q=SELECT+COUNT()+FROM+Account"
        try:
            resp = requests.get(url, headers={"Authorization": header}, timeout=30)
            print(f"\n3) Direct REST call, header '{label}', API v{v}: HTTP {resp.status_code}")
            print("   response:", resp.text[:200])
        except Exception as exc:  # noqa: BLE001
            print(f"\n3) Direct REST call, header '{label}', API v{v}: failed: {exc}")
