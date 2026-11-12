# B2B Service Agent on Salesforce (Agentforce + Claude)

An AI customer-service agent for **Delta Industrial Supplies**, a fictional B2B supplier of
industrial parts and building materials. The agent answers order-status and product
questions, takes quote requests and logs complaints in Salesforce, with guardrails, an
evaluation set and monitoring.

> Learning project, built in November 2026 to learn the Salesforce / Agentforce / Claude stack
> end to end, following the Forward Deployed Engineer way of working.

## Status
🚧 In progress: Step 5 of 9 done.

## Planned structure
| Folder | Contents |
|---|---|
| `force-app/` | Salesforce metadata (objects, Flows, Apex, agent), deployed with the Salesforce CLI |
| `data/` | Python scripts that generate synthetic B2B data |
| `tests/` | API tests for the agent actions (Flows), run through the Salesforce CLI |
| `claude_agent/` | Claude agent connected to Salesforce through MCP / REST API |
| `evals/` | Test set, evaluation script and quality/cost report |
| `docs/` | Use-case brief, architecture diagram, demo script |

## Screenshots

**Get Order Status flow (agent action for order status).** It looks up the customer's
account first, then the order *within that account only*, so a customer can never see another
company's order.

![Get Order Status flow in Flow Builder](docs/images/get-order-status-flow.png)

**Guardrail test in Flow Builder's Debug mode.** Customer `C-1001` asks for order `SO-10447`,
which belongs to another company. The order lookup finds nothing, and the flow returns the
standard "not found" message.

![Debug run of the guardrail case](docs/images/get-order-status-guardrail-debug.png)

## Tech
Salesforce Developer Edition · Agentforce · Flows · Apex · Salesforce CLI · Python · Claude API · MCP
