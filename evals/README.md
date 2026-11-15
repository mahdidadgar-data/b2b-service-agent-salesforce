# Evaluation: Delta Service Agent (Step 8)

One evaluation set for both agents: the Agentforce agent (`Delta_Service_Agent`) and Claude via
the hosted MCP server (Step 7). The expected values were cross-checked against the org on
13 Nov 2026 (orders, products, datasheets, and the product search simulated on the org data).

## Files

| File | What it is |
|---|---|
| `eval-set.csv` | **The single source**: 52 tests, one row per test |
| `results/TEMPLATE.csv` | Column layout for a results file (one row per test and run) |
| `results/agentforce-v4-<date>.csv` | Results of the automated Agentforce runs |
| `results/raw/` | Raw CLI output and traces per run (**gitignored**: record IDs, user names) |
| `agentforce/run_preview.py` | Runner for the automated read-only Agentforce tests |

## Columns of `eval-set.csv`

| Column | Meaning |
|---|---|
| `id` | O = order status, G = order guardrails, P = product specs, D = product guardrails, L/S = language and context, E/X = escalation and off topic, W = write actions |
| `section` | A–F, W |
| `platform` | `Both`, `AF` (Agentforce only: write actions), `CL` (Claude only) |
| `af_runner` | How the Agentforce side runs: `auto` (the runner), `manual` (builder Preview as the agent user), `n/a` (Claude only) |
| `lang` | EN, NL, or a switch such as NL→EN |
| `turn1`–`turn3` | The customer's messages, one per turn, in one session. Every test starts in a fresh session |
| `expected` | Expected behaviour (values checked against the org) |
| `pass_criterion` | What decides pass/fail. Only this counts |
| `tag` | `ACC` (accuracy), `LEAK` (data or price leak), `HAND` (hand-off / out of scope) |
| `expect_tool` | `yes`, `no`, `any` (not scored), or `yes:2` / `yes:1,2` (must be called in those turns) |
| `data_ref` | The order or product the test is about |
| `notes` | Caveats, e.g. when the search term the model passes decides the result |

## Success criteria (from the use-case brief)

| Criterion | Target | Measured on |
|---|---|---|
| Answer accuracy | ≥ 90 % | tests tagged `ACC` |
| Correct hand-off | 100 % | tests tagged `HAND` |
| Data leaks | 0 | tests tagged `LEAK` (one failure = criterion failed) |
| Containment | ≥ 60 % | share of `ACC` tests answered without a human |

## Results 15 Nov 2026

| Platform / version | Tests | ACC | LEAK | HAND | Results |
|---|---|---|---|---|---|
| Agentforce v4 | 43 automated | 24/26 = 92 % | 10/10 | 5/7 = 71 % | [agentforce-v4-2026-11-15.csv](results/agentforce-v4-2026-11-15.csv) (+ [pilot 13 Nov](results/agentforce-v4-2026-11-13.csv)) |
| Agentforce v5 | 51 (43 automated + 8 manual) | 32/32 | 11/11 | 8/8 | [agentforce-v5-2026-11-15.csv](results/agentforce-v5-2026-11-15.csv) |
| Claude, Opus 5.5 (claude.ai Project) | 45 | 26/26 | 11/11 | 8/8 | [claude-opus55-2026-11-15.csv](results/claude-opus55-2026-11-15.csv) |

- v4 failed the hand-off criterion (O-07, P-09, D-04, E-02 failed); v5 fixes all four and meets
  all criteria. v5 is version 5 of `Delta_Service_Agent` (Inactive).
- Claude: claude.ai switched G-06, G-07 and G-08 to Opus 4.8; they passed, but the run isn't on
  one fixed model.
- Containment is 100 % **on this test set**; real containment has to come from production logs.
- The write tests (W-01…W-07) and E-04 ran manually in the builder Preview as the agent user;
  every created record was checked and deleted by Id.

Details and lessons: [learning log, Step 8](../docs/learning-log.md).

## How to run

**Agentforce, automated (43 read-only tests):**
```powershell
python evals/agentforce/run_preview.py                               # plan only, starts nothing
python evals/agentforce/run_preview.py --ids O-01,G-01 --confirm      # a subset
python evals/agentforce/run_preview.py --confirm                     # all automated tests
```
- Uses `sf agent preview` on the authoring bundle `Delta_Service_Agent_4` with live actions, so
  **no activated agent version is needed**. One fresh session per test.
- Tool calls and their inputs come from `sf agent trace read` (dimension `actions`); subagents
  from dimension `routing`.
- **Never runs W-tests or E-04**, and never sends a confirmation. A write guard counts new Cases and
  Opportunities after every test and stops the run if there are any. It reports them and never
  deletes them.
- `pass` and `failure_type` are left empty: a person judges each row against `pass_criterion`,
  reading the tool columns as well as the answer.

**Agentforce, manual (W-01…W-07, E-04):** in the Agentforce Builder Preview, which runs as the agent
user. Run the W-tests once, record the case and QR numbers, then delete the created records (admin,
by Id). Every run uses up case and QR numbers.

### Which user runs the actions in the CLI preview?
- **The CLI preview trace doesn't say.** The pilot (13 Nov 2026, O-01 and G-01) searched the raw
  trace and the CLI's session files (`.sfdx/agents/<bundle>/sessions/`): no user ID, username or
  org ID. The only "identity" field is a toxicity-score category, and the session metadata only
  says `"mockMode": "Live Test"`.
- **Read-only results are valid regardless.** The ownership check (customer number + order number
  must belong together) and the product rules (active only, explicit outputs, no prices) are flow
  logic. They behave the same for any running user.
- **W-tests stay manual in the builder Preview.** There the running user is proven: the Step 6a and
  6c Preview records had `CreatedBy` = the agent user. A write through the CLI preview could run as
  someone else (possibly the admin), which would hide a permission gap.

### What the trace gives for monitoring
`sf agent trace read --format detail --dimension actions` returns per action: the action name,
its input and output, `error`, and **`latencyMs`** (pilot: `Get_Order_Status` 1626 ms for a found
order, 331 ms for not found). That is action latency only, not the full answer time (model
reasoning comes on top). The runner keeps the raw trace files, so latency can be added to the
results later without new runs. Dimension `routing` gives the subagent per turn (`toTopic`).

**Claude (45 tests):** in the claude.ai Project "Delta Service Agent (Claude)", one new
conversation per test, **one fixed model for the whole run** (record it in
`agent_version_or_model`). Copy the tool input from the tool block in the chat.

## Rules for a fair run
- Fresh session per test ID; multi-turn tests are typed turn by turn in the same session.
- Record the **tool input**, not only the answer: for product searches, a "not found" can come from
  the search term the model passes ("the pump", "13mm") rather than from the flow.
- Don't use C-1011 + DP-200 or C-1011 + DIS-VLV-BS-DN25 in write tests (open Preview requests
  QR-0003 and QR-0007).
