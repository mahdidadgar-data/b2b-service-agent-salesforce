"""
Minimal Salesforce client that sends every request THROUGH the Salesforce CLI.

Why: recent CLI versions no longer reveal the session token (it is redacted for
security), so a Python library cannot borrow it. Instead we let the CLI, which
holds the session securely and refreshes it, make the authenticated calls:

  - queries:        sf data query --json
  - inserts/updates: sf api request rest  ->  /composite/sobjects (up to 200 records per call)

No token, password or secret ever passes through this code.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

API = "v62.0"
SF = shutil.which("sf") or "sf"


def _run(args):
    result = subprocess.run([SF, *args], capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout, result.stderr


def _parse_json(text):
    """Parse JSON from CLI output, skipping any warning lines printed before it."""
    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    if not starts:
        raise ValueError(f"No JSON in CLI output: {text[:300]}")
    return json.loads(text[min(starts):])


class SalesforceCLI:
    def __init__(self, org=None):
        self.org_args = ["--target-org", org] if org else []

    # ---------------------------------------------------------------- read
    def query(self, soql):
        code, out, err = _run(["data", "query", "--query", soql, "--json", *self.org_args])
        data = _parse_json(out or err)
        if data.get("status") != 0:
            sys.exit(f"Query failed: {data.get('message')}\nSOQL: {soql}")
        return data["result"]["records"]

    # --------------------------------------------------------------- write
    def _composite(self, method, sobject, records):
        """Send up to 200 records per request to the sObject Collections API."""
        ids = []
        for start in range(0, len(records), 200):
            chunk = records[start:start + 200]
            body = {"allOrNone": True,
                    "records": [{"attributes": {"type": sobject}, **r} for r in chunk]}
            fd, path = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(body, f)
            try:
                code, out, err = _run(["api", "request", "rest",
                                       f"/services/data/{API}/composite/sobjects",
                                       "--method", method, "--body", f"@{path}", *self.org_args])
            finally:
                os.remove(path)
            try:
                results = _parse_json(out)
            except ValueError:
                sys.exit(f"{method} {sobject} failed.\n{(out + err)[:1500]}")
            if not isinstance(results, list):
                sys.exit(f"{method} {sobject} failed: {json.dumps(results)[:1500]}")
            failed = [(rec, res) for rec, res in zip(chunk, results) if not res.get("success")]
            if failed:
                # With allOrNone, one bad record makes every other record fail with
                # ALL_OR_NONE_OPERATION_ROLLED_BACK. Show the real (root-cause) errors first.
                def rolled_back(item):
                    codes = {e.get("statusCode") for e in item[1].get("errors", [])}
                    return codes == {"ALL_OR_NONE_OPERATION_ROLLED_BACK"}
                root = [f for f in failed if not rolled_back(f)]
                print(f"  {len(root)} root-cause error(s), "
                      f"{len(failed) - len(root)} record(s) only rolled back:")
                for rec, res in (root or failed)[:5]:
                    print(f"  ERROR {sobject}: {res.get('errors')}\n    record: {rec}")
                sys.exit(f"{len(failed)} {sobject} record(s) failed (nothing in this batch was saved). "
                         "Fix the cause and re-run.")
            ids.extend(res["id"] for res in results)
        return ids

    def insert(self, sobject, records):
        return self._composite("POST", sobject, records) if records else []

    def update(self, sobject, records):
        """records must each contain an 'Id'."""
        return self._composite("PATCH", sobject, records) if records else []
