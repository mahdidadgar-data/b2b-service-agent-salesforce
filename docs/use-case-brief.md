# Use-Case Brief: AI Service Agent for Delta Industrial Supplies

*Version 1.0 (agreed), 11 Nov 2026. Author: Mahdi Dadgar.*
*Learning project. The company and all figures are fictional, but realistic for a mid-sized B2B distributor.*

---

## 1. Context
**Delta Industrial Supplies** is a B2B distributor of industrial parts and building materials
(pumps, valves, pipe fittings, insulation, fixings) in the Netherlands and Belgium.

| Fact (assumed) | Value |
|---|---|
| Business customers | ~3,000 (installers, contractors, facility management companies) |
| Product catalogue | ~8,000 SKUs, each with a technical datasheet |
| Customer service team | 12 FTE |
| Customer contacts | ~1,500 per week (email, phone, customer portal) |
| CRM | Salesforce (Service Cloud + Sales Cloud) |

## 2. Problem statement
Customer service spends most of its time on **repetitive questions** that can be answered
from data already in Salesforce: *"Where is my order?"*, *"What is the max pressure of this
pump?"*, *"Can I get a quote for 40 valves?"*. Customers wait in queues for simple answers, and
specialists have less time for complex cases.

Estimated mix of incoming contacts (assumed):

| Type | Share | Can an agent handle it? |
|---|---|---|
| Order and delivery status | 35% | Yes, fully |
| Product and spec questions | 15% | Yes, if the answer is in the datasheet |
| Quote requests | 10% | Partly: collect requirements, hand over to sales |
| Complaints and returns | 8% | Partly: register the case, hand over to a human |
| Other (invoices, accounts, technical advice) | 32% | No, route to a human |

## 3. Goal
A customer-facing AI service agent that **resolves simple requests end to end** and
**prepares complex ones** for a human, so the team spends its time where it adds value.

## 4. Users and channel
- **Primary users:** buyers and installers at customer companies (logged-in portal users).
- **Secondary users:** customer service agents and sales reps, who receive the handovers.
- **Channel in production:** chat on the customer portal.
- **Channel in this project:** the Agentforce preview in the Developer org, plus a Claude chat
  client connected through MCP.

## 5. Use cases in scope

### UC1: Order and delivery status
- **Example:** *"Where is order 10452?"* / *"When will my valves arrive?"*
- **Data:** Order (number, status, delivery date, carrier/tracking), Account.
- **Action:** look up the order **only within the customer's own account** and report status and expected delivery.
- **Done when:** correct status given, or the customer is told clearly that the order was not found.

### UC2: Product and spec questions
- **Example:** *"What is the max operating pressure of pump DP-200?"* / *"Which valve fits a 1-inch pipe at 80 °C?"*
- **Data:** Product records + product datasheets (Agentforce Data Library, RAG).
- **Action:** answer **only from the datasheet** and name the source product. If the
  answer isn't in the data, say so and offer a hand-off to a product specialist.
- **Done when:** the answer matches the datasheet, with no invented values.

### UC3: Quote request
- **Example:** *"I need a price for 40 ball valves DN25 for a project in Utrecht."*
- **Data:** Product, Account, Opportunity.
- **Action:** collect the required details (products, quantities, delivery location and date)
  and **create an Opportunity** for the sales team. The agent **never quotes prices or discounts**.
- **Done when:** the Opportunity exists with complete details and the customer is told when sales will respond.

### UC4: Complaint or return
- **Example:** *"Three of the fittings we received are cracked."*
- **Data:** Order, Case.
- **Action:** register a **Case** linked to the order, set the priority (high if it involves
  safety or a stopped project), and **hand over to a human**.
- **Done when:** the Case exists with order reference, description and priority.

## 6. Out of scope (the agent must hand over)
- Technical design or installation advice beyond the datasheet (safety and liability).
- Prices, discounts, credit, payment terms, invoices.
- Changing or cancelling orders (phase 2, after the pilot).
- Legal claims, angry or threatening customers, and any request about another company's data.

## 7. Data foundation
| Object | Use | Notes |
|---|---|---|
| Account / Contact | Who the customer is | Each portal user belongs to one Account |
| Product2 | Catalogue | Key specs as fields (pressure, temperature, size, material) |
| Order (+ items) | Order status | **Standard Salesforce Order** with Order Products, a Price Book and custom delivery fields (decision 11 Nov: standard objects before custom ones) |
| Case | Complaints and returns | Standard Service Cloud object |
| Opportunity | Quote requests | Standard Sales Cloud object |
| Datasheets (PDF/text) | Spec answers | Indexed in the Agentforce Data Library |

**Data quality risk:** the agent is only as good as the data. Missing delivery dates or
outdated datasheets lead directly to wrong answers. Data readiness is checked **before** building.

## 8. Guardrails and risks
| Risk | Guardrail |
|---|---|
| Customer sees another company's orders | Every lookup is filtered by the logged-in user's Account. The agent never searches across accounts |
| Invented specs (hallucination) | Answers only from retrieved product data. "I don't know" plus hand-off is allowed and preferred |
| Unsafe technical advice | Out of scope. Fixed hand-off message with a specialist contact |
| Price or discount commitments | Not allowed. Quote requests go to sales as an Opportunity |
| Prompt injection ("ignore your instructions…") | Instructions stay fixed and actions have limited permissions. Tested in the eval set |
| Personal data | Only data needed for the request. No sensitive data in logs or prompts |

## 9. Success metrics
| Metric | Target for the pilot |
|---|---|
| Accuracy on the test set (correct answer or correct hand-off) | ≥ 90% |
| Correct hand-off on safety / out-of-scope questions | 100% |
| Cross-account data leaks in tests | 0 |
| Share of UC1 + UC2 conversations resolved without a human (containment) | ≥ 60% |
| Cost per conversation (tokens / credits) | Measured and reported |
| Customer satisfaction (post-chat rating) | Baseline in the pilot, then improve |

## 10. Evaluation plan
- A test set of **40 questions**: ~10 per use case, plus out-of-scope, safety and prompt-injection cases.
- Each test has the expected outcome (answer, action, or hand-off).
- Run before go-live and again after every change (regression testing).
- After go-live, monitor quality, drift, hand-off rate and cost per conversation.

## 11. Delivery approach
1. **Discovery:** this brief, agreed with the business owner.
2. **Data foundation:** model and clean the data the agent needs.
3. **Build:** topics, instructions, actions (Flows / Apex), knowledge (Data Library).
4. **Test:** evaluation set, guardrail and security tests.
5. **Pilot:** a small group of friendly customers, with close monitoring.
6. **Go-live and hypercare:** monitor, tune and report, then plan phase 2.

## 12. Open questions for the client
- Who is the business owner and who signs off the guardrails?
- How are portal users identified (login, account number)?
- Are the datasheets current, and who maintains them?
- What response time does sales promise for quote requests?
- What is the escalation path outside office hours?

## 13. Scope of this learning project
UC1–UC4 are built in a Salesforce Developer org with synthetic data, tested with the evaluation
set, and compared with a Claude agent on the same data through MCP. No real customers or
production data are involved.
