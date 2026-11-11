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
  Instance: `https://orgfarm-60adaaa1ee-dev-ed.develop.my.salesforce.com`
- Available in Setup: Agentforce Studio, Agentforce Data Library, Agentforce Registry
  (Registered APIs, **Registered MCP Servers**), Agentforce Gateway, Einstein Generative AI.
- GitHub: https://github.com/mahdidadgar-data/b2b-service-agent-salesforce (branch `main`).

## Progress log
- **Step 1 (11 Nov):** setup done: Dev org, CLI auth, Salesforce DX project skeleton, first commit `908cf06`.
- **Step 2 (11 Nov):** use-case brief v1.0 agreed (`docs/use-case-brief.md`), commit `28d4bf5`.
- **Step 3 (11 Nov):** data foundation: 19 custom fields + permission set `Delta_Data_Access` deployed;
  synthetic data loaded (29 products, 12 accounts, 16 contacts, 40 activated orders, 91 order items,
  4 cases, 3 opportunities). Customer key: `Account.Customer_Number__c` (C-1001…C-1012); order key: `Order.Name` (SO-…).

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
- **Learning log:** after each step, add a section to `docs/learning-log.md` (what was done, what was
  learned, problems and solutions, link to the FDE role, possible interview questions). At the end it
  becomes a printable PDF with a full interview-question section. Keep the steps in order (Step 1, 2, 3, ...).
