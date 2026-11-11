# B2B Service Agent on Salesforce (Agentforce + Claude)

An AI customer-service agent for **Delta Industrial Supplies**, a fictional B2B supplier of
industrial parts and building materials. The agent answers order-status and product
questions, takes quote requests and logs complaints in Salesforce, with guardrails, an
evaluation set and monitoring.

> Learning project, built in November 2026 to learn the Salesforce / Agentforce / Claude stack
> end to end, following the Forward Deployed Engineer way of working.

## Status
🚧 In progress: Day 1 (setup).

## Planned structure
| Folder | Contents |
|---|---|
| `force-app/` | Salesforce metadata (objects, Flows, Apex, agent), deployed with the Salesforce CLI |
| `data/` | Python scripts that generate synthetic B2B data |
| `claude_agent/` | Claude agent connected to Salesforce through MCP / REST API |
| `evals/` | Test set, evaluation script and quality/cost report |
| `docs/` | Use-case brief, architecture diagram, demo script |

## Tech
Salesforce Developer Edition · Agentforce · Flows · Apex · Salesforce CLI · Python · Claude API · MCP
