# CLAUDE.md: B2B Service Agent on Salesforce

## Why this project exists
Mahdi Dadgar is preparing for an interview on **Friday 20 November 2026** for the
**Agentforce Forward Deployed Engineer (FDE)** role at Nextview Consulting, a Salesforce
and Anthropic partner. The interviewer (Daan Elshout, Data, Analytics & AI Consultant) will
cover background, technical experience, **how to approach building and deploying AI agents
with customers**, and what FDE work looks like in practice.

This project is a learning and portfolio project. It follows the full FDE workflow end to end
so Mahdi can learn the Salesforce/Agentforce stack and answer those questions with concrete
examples. Present it honestly as a learning project, not client work.

## How to work with Mahdi
- Act as a senior AI engineer who teaches and builds alongside him. Explain *why* before *how*.
- Give step-by-step, copy-paste-ready commands for **Windows (PowerShell)**.
- Be realistic. Say clearly when something is a limitation of a free Developer org.
- Don't skip steps. Mahdi is new to Salesforce. He is strong in Python, SQL, ML and RAG/LLMs.
- Commit small, meaningful steps to Git with clear messages.

## The business case (fictional)
**Delta Industrial Supplies** is a B2B supplier of industrial parts and building materials
(pumps, valves, fittings, insulation) that sells to installers and contractors. Its customer
service team spends most of its time on repetitive questions.

Agent use cases:
1. **Order and delivery status:** look up an order in Salesforce and report status and ETA.
2. **Product and spec questions:** answer from product data and datasheets.
3. **Quote requests:** collect the requirements and create an Opportunity for sales.
4. **Complaints and returns:** create a Case with priority and hand over to a human when needed.

## Architecture (target)
- Salesforce Developer Edition org, with the configuration kept in Git via the Salesforce CLI (`sf`).
- Data model: Account (customer companies), Contact, Product2, custom Order objects, Case, Opportunity.
- Synthetic data generated with Python (`data/`).
- Agentforce agent: topics + actions (Flows, one Apex invocable action).
- Claude agent connected to the same Salesforce data through MCP / REST API (`claude_agent/`).
- Evaluation: a test set of 30–50 questions, an eval script, guardrails, and a quality and token-cost report (`evals/`).
- Docs: use-case brief, architecture diagram, demo script (`docs/`).

Fallback: if Agentforce is too limited in the free org, the Claude agent on Salesforce data
becomes the main demo.

## Environment (as of Day 1, 11 Nov 2026)
- Windows, VS Code, PowerShell. Salesforce CLI 2.157, Git 2.55, Python 3.12.
- Salesforce Developer Edition org (with Agentforce), CLI alias **`delta-dev`** (default org).
  Instance: `https://<your-org>.develop.my.salesforce.com` (placeholder; the real instance URL is
  available locally via `sf org display --target-org delta-dev` and is not stored in Git).
- Available in Setup: Agentforce Studio, Agentforce Data Library, Agentforce Registry
  (Registered APIs, **Registered MCP Servers**), Agentforce Gateway, Einstein Generative AI.
- GitHub: https://github.com/mahdidadgar-data/b2b-service-agent-salesforce (branch `main`).

## Progress log
- **Step 1 (11 Nov):** setup done: Dev org, CLI auth, Salesforce DX project skeleton, first commit `908cf06`.
- **Step 2 (11 Nov):** use-case brief v1.0 agreed (`docs/use-case-brief.md`), commit `28d4bf5`.
- **Step 3 (11 Nov):** data foundation: 19 custom fields + permission set `Delta_Data_Access` deployed;
  synthetic data loaded (29 products, 12 accounts, 16 contacts, 40 activated orders, 91 order items,
  4 cases, 3 opportunities). Customer key: `Account.Customer_Number__c` (C-1001…C-1012); order key: `Order.Name` (SO-…).
  Commit `3e72e4f`.
- **Step 4 (11 Nov):** first agent action: flow `Get_Order_Status` (built in Flow Builder, retrieved to Git),
  API tests in `tests/run_flow_tests.py`, screenshots. Commit `469e83c`.
- **Step 4b (11 Nov):** flow hardened as version 2 (blank-input guard), deployed from Git; v2 active, v1 obsolete.
  Open limitation for Step 5: the customer number must come from the logged-in user, not from the chat.
- **Step 5 (12 Nov):** Agentforce agent `Delta_Service_Agent` built in the new Agentforce Builder (Agent Script)
  from the Service Agent template, scoped to Agent Router, Order Inquiries, Escalation, Off Topic, Ambiguous
  Question; action Get Order Status (our flow); Dutch added to Allowed Languages; Version 1 committed.
  Agent user needed read-only object access on Account and Order (commit `4e87038`).
  Retrieved metadata: `AiAuthoringBundle` (Agent Script source), `Bot`/`BotVersion`, `GenAiPlannerBundle`,
  `AiAgentDefinition`/`AiAgentDefinitionVersion` (generated at Commit Version; generated `.agent` files are base64).
  6 Preview tests pass. Open for Step 8: static English welcome, Ambiguous Question has no exits,
  real escalation needs Omni-Channel, identity still from the typed customer number.
- **Step 6a (12 Nov):** flow `Create_Complaint_Case` written as metadata (v2 active: unknown-customer message
  without order number, fault path on create/read-back), duplicate protection per order. Permission sets split
  per role: `Delta_Data_Access` = humans/admin (unchanged), `Delta_Agent_Access` = agent user only (read Account/
  Order, read+create Case, Case.AccountId/Related_Order__c/Created_By_Agent__c editable). Assignment script
  `scripts/setup-agent-permissions.ps1`. Tests: 12/12 pass, complaint suite cleans up its own cases.
  Do not use `ORDER BY PermissionSet.Name` on PermissionSetAssignment (drops rows).
- **Step 6a wrap-up (12 Nov):** agent **Version 2** committed and retrieved (`*_2` / `_v2` / `#2` components):
  Complaints subagent + Create Complaint Case action (require user confirmation ON, orderNumber optional),
  transitions Complaints↔Escalation/Order Inquiries, Off Topic→Complaints. 4 Preview tests pass; Preview cases
  had CreatedBy = agent user (proof of agent permissions), then deleted. API tests 13/13 (test g added).
  Open for Step 8: platform confirmation text promises a case before the ownership check.
- **Step 6b (12 Nov):** flow `Get_Product_Specs` v3 (exact match first, then word-based: every word in Name/
  ProductCode/`Search_Keywords__c`, longest word as pre-filter, literal recheck of all words; fail closed, active
  only, explicit field list, no prices/stock, cap 10 names). New field `Product2.Search_Keywords__c` (Dutch/English
  synonyms; agent read-only, admin read+edit) seeded via `data/update_product_keywords.py`. The 17 Developer
  Edition sample products deactivated (`scripts/deactivate-sample-products.ps1`). Agent **Version 3** committed
  in the builder (not activated) and retrieved: Product Information subagent, bilingual welcome, "language of the
  most recent message". API tests 32/32; Preview tests 1–9 pass. Open items consolidated at the end of the log.
- **Step 6c (12 Nov):** flow `Create_Quote_Request` (v1): quote request → Opportunity. Reuses `Get_Product_Specs`
  as a subflow (one search for specs and quotes); no OpportunityLineItem (needs a price; the agent never prices);
  5 new Opportunity fields (`Requested_Product__c`, `Requested_Quantity__c`, `Quote_Request_Number__c` auto-number
  `QR-{0000}`, `Created_By_Agent__c`, `Customer_Note__c`); duplicate = account + product, agent-created only;
  quantity whole 1–10,000 (2.5 rejected); note cut to 255. Agent user: Opportunity read + create only. Finding:
  the Einstein Agent User profile grants FLS on Amount/ExpectedRevenue/Probability (permission sets only add).
  `Get_Product_Specs` v4: plural tolerance (stem rule) + irregular Dutch plurals as keywords (21 products).
  Agent **Version 4** committed in the builder (not activated) and retrieved: Quote Request subagent. API tests
  54/54; Preview tests 1–6 (QR-0003 and QR-0007 on C-1011 are Preview evidence: leave them alone).

## Timeline
| Day | Date | Goal |
|---|---|---|
| 1 | Nov 11 | Setup: Dev org, GitHub repo, Salesforce CLI, project structure, first commit |
| 2 | Nov 12 | Trailhead basics (Salesforce, Flow, Apex, Agentforce) + use-case brief |
| 3–4 | Nov 13–14 | Data model, synthetic data, first Flow |
| 5–6 | Nov 15–16 | Agentforce agent: topics, actions, guardrails |
| 7 | Nov 17 | Claude agent via MCP on the same data |
| 8 | Nov 18 | Tests, evaluation, monitoring report, README |
| 9 | Nov 19 | Demo rehearsal + interview answers |

## Conventions
- Never commit secrets (`.env`, auth files, API keys). Use `.env` locally and keep `.env.example` in Git.
- Python 3, with dependencies in `requirements.txt`.
- Write in plain, professional English.
- **Salesforce API access from Python goes through the CLI** (`data/sf_cli.py`). CLI 2.157 redacts the
  access token, so never try to extract, print or store a token.
- **Validate before loading:** run `data/preflight.py` before `data/load_data.py` whenever the generator changes.
- **Generator: `--only products`; never regenerate orders without a fixed date.** Order, case and opportunity
  dates are relative to `date.today()`, so a full regeneration on another day shifts every date and breaks the
  match with the org (and the order tests). `python data/generate_data.py --only products` is safe (no dates,
  no randomness). A fixed reference date is on the Step 8 list.
- **Product keywords** (`Product2.Search_Keywords__c`, matching only, never an output): keywords may add names
  and synonyms, never properties the data doesn't confirm (check material words against `Material__c`).
- **Tests that create records use up auto-numbers.** The complaint and quote suites delete their own records,
  but case numbers and `QR-…` numbers are never reused, so every run leaves gaps. Fine in this Developer org;
  in a real project, run these tests in a sandbox. Don't use C-1011 + DP-200 or C-1011 + DIS-VLV-BS-DN25 in
  tests (open Preview requests QR-0003 and QR-0007).
- **Learning log:** after each step, add a section to `docs/learning-log.md` (what was done, what was
  learned, problems and solutions, link to the FDE role, possible interview questions). At the end it
  becomes a printable PDF with a full interview-question section. Keep the steps in order (Step 1, 2, 3, ...).
