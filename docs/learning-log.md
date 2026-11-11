# Learning Log: B2B Service Agent on Salesforce

This log records every step of the project: what I did, what I learned, the problems I hit
and how I solved them, and how each step connects to the Forward Deployed Engineer (FDE)
role. At the end it becomes a printable PDF with interview questions.

---

## Step 1 (Day 1, 11 Nov 2026): Environment and project setup

### Goal
Prepare a professional working environment before building anything: a Salesforce org, the
tools on my computer, and a Git repository that holds the Salesforce configuration as code.

### What I did
1. **Created a free Salesforce Developer Edition org.** It came with Agentforce and Data Cloud
   features. Salesforce generated my username automatically (`...@agentforce.com`), which is
   different from my personal email.
2. **Created a public GitHub repo** `b2b-service-agent-salesforce`, empty (no README or
   .gitignore), so the first upload from my computer would not conflict.
3. **Installed the Salesforce CLI** (`sf`, version 2.157) and checked my tools:
   `sf --version`, `git --version` (2.55), `python --version` (3.12).
4. **Set up the project folder** with the base files of a Salesforce DX project:
   - `sfdx-project.json`: marks the folder as a Salesforce project and points to `force-app/`
   - `force-app/main/default/`: where all Salesforce metadata will live
   - `.forceignore`: files the CLI must never deploy
   - `.gitignore`: files Git must never upload (login tokens, secrets)
   - `README.md`: the front page of the repo
   - `CLAUDE.md`: project context for Claude Code (AI-assisted development)
5. **Connected the folder to my org** with the CLI:
   ```powershell
   sf org login web --alias delta-dev --set-default --instance-url https://orgfarm-60adaaa1ee-dev-ed.develop.my.salesforce.com
   ```
6. **Made the first commit and pushed it to GitHub:**
   ```powershell
   git init
   git branch -M main
   git remote add origin https://github.com/mahdidadgar-data/b2b-service-agent-salesforce.git
   git add .
   git status
   git commit -m "Day 1: project setup - Salesforce DX project, README, project context"
   git push -u origin main
   ```
7. **Checked that Agentforce is available** in Setup: Agentforce Studio, Data Library,
   Registry (with Registered MCP Servers) and Gateway are all present.

### What I learned
- **Org:** a Salesforce org is one company's own Salesforce environment, with its own data,
  users and configuration. A Developer Edition org is a free one for learning and building.
- **Salesforce DX / "configuration as code":** professional teams don't only click things
  together in Setup. They keep the configuration (objects, fields, Flows, Apex, agents) as files
  in Git and deploy it with the CLI. That makes changes reviewable, repeatable and reversible.
- **Salesforce CLI (`sf`):** the command-line tool that connects my folder to an org. The
  **alias** (`delta-dev`) is a nickname, so every command goes to the right org.
- **OAuth login:** `sf org login web` opens a browser. I log in, Salesforce sends a code back to
  my computer (`localhost:1717`), and the CLI stores a secure token in `.sf/` and `.sfdx/`.
  These folders are secrets and must never go to GitHub.
- **Git basics:** `init` (start tracking), `remote add` (link to GitHub), `add` (choose files),
  `status` (check before committing), `commit` (save a snapshot), `push` (upload).
- **Check before you commit:** `git status` is the moment to catch secrets or wrong files.

### Problems I hit and how I solved them
| Problem | Cause | Solution |
|---|---|---|
| The installer kept reappearing after "Close" | The installer had been started several times | Installation was already complete. Cancelled the extra windows |
| Login in VS Code rejected my password | I used my email as the username. Salesforce had generated a different username (`...@agentforce.com`) | Found the real username under Settings and used it |
| Browser showed "localhost refused to connect" | The CLI command had timed out, so nothing was listening for the login code | Ran the login command again and finished it within the time window |
| Git warning "LF will be replaced by CRLF" | Windows and Linux end lines differently | Normal on Windows. Git handles it automatically |

### Link to the FDE role
An FDE starts every engagement by setting up a safe, reproducible environment: access to the
client's org, source control, and a clean way to deploy. Secrets are protected from the first
commit. This step is that foundation.

### Possible interview questions
- *Why keep Salesforce configuration in Git instead of only configuring in Setup?*
- *How do you make sure credentials and tokens never end up in a repository?*
- *What is a Salesforce org, and why would you work in a sandbox or developer org first?*

---

## Step 2 (Day 1, 11 Nov 2026): Discovery and the use-case brief

### Goal
Define *what* the agent should do, for whom, with which data, within which limits, and how
success is measured, before building anything.

### What I did
1. Logged in to **Trailhead** (Salesforce's free learning platform) with my Salesforce account
   and read the basics: Platform Basics, Data Modeling, Flow, Apex and Agentforce.
2. Wrote the **use-case brief** (`docs/use-case-brief.md`) for the fictional client Delta
   Industrial Supplies and agreed it as version 1.0.
3. Made two design decisions:
   - **Four use cases:** order status (resolve), product specs (resolve), quote request
     (prepare for sales), complaint/return (prepare for a human).
   - **Standard Salesforce `Order` object** instead of a custom object.

### What I learned
- **An FDE starts with the business problem, not the technology.** The brief is the first
  deliverable an FDE agrees with the client.
- **Choose use cases by volume and feasibility.** Order status is 35% of contacts and fully
  answerable from data, so it's the best first use case.
- **Three levels of agent work:**
  - *Resolve:* the agent finishes the request itself (order status, spec question).
  - *Prepare:* the agent collects information and creates a record for a human (quote → Opportunity, complaint → Case).
  - *Hand over:* the agent recognises it must not answer (safety advice, prices, legal).
- **Out of scope is as important as in scope.** Defining what an agent must *not* do is
  part of the design.
- **Guardrails in B2B:** the biggest risk is one customer seeing another company's data. Every
  lookup must be filtered by the customer's own Account.
- **Hallucination control:** the agent answers only from retrieved data. "I don't know" plus a
  hand-off is better than a confident wrong answer.
- **Success metrics before building:** accuracy on a test set (≥ 90%), correct hand-off on safety
  questions (100%), zero data leaks, containment rate, cost per conversation.
- **Standard vs custom objects:** Salesforce best practice is to use standard objects (Account,
  Order, Case, Opportunity) before creating custom ones. Standard objects bring built-in features,
  reports and integrations, and clients already know them.
- **An FDE always lists open questions for the client**, such as who signs off the guardrails
  and who maintains the datasheets.

### Link to the FDE role
The vacancy says the FDE works on site with client teams "to identify the use cases where agents
add the most value" and explains "results and trade-offs to client management in plain language".
The use-case brief is exactly that conversation, written down.

### Possible interview questions
- *How do you approach building and deploying an AI agent with a customer?*
  Start with the problem and contact mix → pick use cases → check data readiness → define
  guardrails and success metrics → build → test against an evaluation set → pilot → go-live →
  monitor.
- *How do you decide which use case to start with?*
- *What should an agent never do, and how do you enforce that?*
- *How would you prevent a customer from seeing another customer's data?*
- *How do you measure whether an agent is successful?*
- *Why did you choose the standard Order object instead of a custom object?*

---

## Step 3 (Day 1, 11 Nov 2026): Data foundation

### Goal
Give the agent realistic data to work with. Extend the standard Salesforce objects with the
fields the four use cases need, make those fields visible to users, generate synthetic data
in Python, and load it into the org in the right order.

### What I did
1. **Added custom fields to standard objects** (decision from the brief: standard objects
   before custom ones), kept as metadata in `force-app/main/default/objects/`:

   | Object | Field | Type | Used for |
   |---|---|---|---|
   | Account | `Customer_Number__c` | Text(20), unique, external ID | Stable customer key (e.g. `C-1001`) |
   | Account | `Customer_Segment__c` | Picklist: Installer, Contractor, Facility Management, Industrial | Segmentation |
   | Product2 | `Category__c` | Picklist: Pumps, Valves, Fittings, Insulation, Fixings | UC2 filtering |
   | Product2 | `Max_Pressure_bar__c` | Number(6,1) | UC2 spec answers |
   | Product2 | `Min_Temperature_C__c`, `Max_Temperature_C__c` | Number(5,0) | UC2 spec answers |
   | Product2 | `Connection_Size__c` | Text(30) | UC2 spec answers |
   | Product2 | `Material__c` | Text(60) | UC2 spec answers |
   | Product2 | `Datasheet_Text__c` | Long Text Area(32768) | UC2 grounding text (later: Data Library) |
   | Order | `Delivery_Status__c` | Picklist: Received, In Preparation, Shipped, Delivered, Delayed | UC1 status |
   | Order | `Expected_Delivery_Date__c` | Date | UC1 ETA |
   | Order | `Carrier__c`, `Tracking_Number__c` | Text(60), Text(40) | UC1 tracking |
   | Order | `Delay_Reason__c` | Text(255) | UC1 explanation for delays |
   | Case | `Related_Order__c` | Lookup(Order), set to null on delete | UC4 link to the order |
   | Case | `Created_By_Agent__c` | Picklist: Agentforce, Claude Agent, Human | Measuring agent vs human cases |
   | Opportunity | `Requested_Items__c` | Long Text Area(5000) | UC3 quote details |
   | Opportunity | `Delivery_Location__c` | Text(120) | UC3 quote details |
   | Opportunity | `Requested_Delivery_Date__c` | Date | UC3 quote details |

2. **Created the permission set `Delta_Data_Access`** with read and edit access to all 19
   custom fields, deployed it, and assigned it to my user:
   ```powershell
   sf project deploy start --source-dir force-app
   sf org assign permset --name Delta_Data_Access
   ```
3. **Wrote two separate scripts:**
   - `data/generate_data.py`: pure Python, no Salesforce connection. Writes JSON files to
     `data/generated/` (29 products, 12 accounts, 16 contacts, 40 orders with 91 order lines,
     4 cases, 3 opportunities). Fixed random seed, so the output is reproducible.
   - `data/load_data.py`: reads the JSON and loads it into the org through the Salesforce CLI
     (`data/sf_cli.py`). It refuses to run if Delta customers already exist, to avoid duplicates.
4. **Loaded the data in dependency order** (a record can only point to a record that already exists):
   1. Product2
   2. Activate the Standard Price Book, then one PricebookEntry per product
   3. Account
   4. Contact (needs AccountId)
   5. Order as *Draft* (needs AccountId and Pricebook2Id)
   6. OrderItem (needs OrderId and PricebookEntryId)
   7. Set Orders to *Activated* (an Order needs at least one product before it can be activated)
   8. Case (needs AccountId and `Related_Order__c`)
   9. Opportunity (needs AccountId)
5. **Verified in the org** with `sf data query`:

   | Object | Records |
   |---|---|
   | Product2 / PricebookEntry | 29 / 29 |
   | Account / Contact | 12 / 16 |
   | Order (all Activated) | 40: Delivered 14, Shipped 8, In Preparation 7, Received 6, Delayed 5 |
   | OrderItem | 91 |
   | Case / Opportunity | 4 / 3 |

### What I learned
- **Field-level security (FLS):** deploying a new field does not make it visible. Every field
  has read and edit permissions per profile or permission set, and until someone is granted
  them, the field is hidden from everyone, including the System Administrator in the UI and
  in API queries. A **permission set** is the clean way to grant that access: it is additive,
  lives in Git next to the fields, and can later be assigned to the agent's user too. That
  matters for the guardrails: the agent can only see what its permissions allow.
- **Standard Order rules:** an Order needs a Price Book, every Order Product needs a
  PricebookEntry, the Standard Price Book must be active, and an Order can only be activated
  once it has products. That is why the load runs in steps and activates at the end.
- **External ID:** `Customer_Number__c` is unique and an external ID. It is the stable
  business key the agent and the eval set use, instead of Salesforce record IDs, which change
  between orgs.
- **Generate vs load:** keeping generation separate from loading makes the data reviewable in
  Git, reproducible, and reusable as ground truth for the evaluation set (the eval script can
  compare the agent's answers with the JSON).
- **Picklists:** `Account.Type` is an unrestricted standard picklist, so the API accepts any
  value without complaining. The generator used `Customer`, which is not a value in this org,
  so I changed it to `Customer - Direct`. An unrestricted picklist does not protect data quality.
- **The sObject Collections API** (`/composite/sobjects`) inserts or updates up to 200 records
  per call. With `allOrNone: true`, a batch either fully succeeds or is fully rolled back, so a
  failed run never leaves half-loaded data behind.

### Problems I hit and how I solved them

**1. Two wrong hypotheses, tested one at a time.** The first loader used the Python library
`simple-salesforce` with the access token from `sf org display --json`. Every call was rejected
with `INVALID_AUTH_HEADER`.
- *Hypothesis A: the session expired* (about two hours had passed since login). Fix: make one
  call through the CLI first, so the CLI refreshes the token. Result: same error, so A was wrong.
- *Hypothesis B: the CLI hides the token unless `--verbose` is used.* Fix: add `--verbose` and a
  check that the token looks like a real session token. Result: same error, so B alone was not it.

After two guesses that did not change the result, I stopped guessing and measured.

**2. Token redaction, found with a diagnostic script.** `data/check_connection.py` checks
the connection step by step, without printing the token itself. It showed that the **CLI**
could query the org without problems, but the value it handed out as `accessToken` was not a
usable token: CLI 2.157 **redacts** the access token in its output, even with `--verbose`. So
the session was fine; Python simply never received a real token.

**3. Redesign: call the API through the CLI.** Instead of trying to extract the token (the
CLI hides it on purpose), `data/sf_cli.py` lets the CLI make every authenticated call:
`sf data query --json` for reads and `sf api request rest` against `/composite/sobjects` for
writes. The CLI keeps and refreshes the session; no token, password or secret ever passes
through Python. This is also the safer design.

**4. allOrNone hides the root cause.** The Product2 insert failed with 29 errors, and the
first five printed were all `ALL_OR_NONE_OPERATION_ROLLED_BACK`. That message only says
"this record was fine, but rolled back because another record failed". I changed `sf_cli.py`
to separate root-cause errors from rolled-back records and print the real ones first. Result:
**4 root-cause errors, 25 only rolled back.** The real error was `STRING_TOO_LONG` on
`Connection_Size__c`: four insulation products had values like
`Wall thickness 13 mm, for pipe 15-54 mm` (39–43 characters) in a Text(30) field.

**5. Fix the data, not the model.** I shortened the values in the generator
(`13 mm wall, pipe 15-54 mm`) instead of widening the field, because the field is a short spec
summary and the full wording stays in the datasheet text. Before loading again, I wrote a
**pre-flight check** that compares every value in the JSON with the org's own field
definitions (`sf sobject describe`: text length, picklist values, field exists). It found the
4 length errors plus the `Account.Type` problem in one run. After the fix: 0 problems, and the
full load succeeded the first time.

| Problem | Cause | Solution |
|---|---|---|
| API calls from Python rejected | CLI 2.157 redacts the access token, so Python had no real token (not an expired session) | Send every call through the CLI (`sf_cli.py`) |
| Only `ALL_OR_NONE_OPERATION_ROLLED_BACK` errors visible | With allOrNone, one bad record rolls back all the others | Print root-cause errors first |
| `STRING_TOO_LONG` on `Connection_Size__c` | 4 insulation values longer than Text(30) | Shortened the values in the generator |
| `Account.Type = 'Customer'` not a valid value | Unrestricted picklist accepts anything | Use the standard value `Customer - Direct` |

### Link to the FDE role
"The agent is only as good as the data" (brief, section 7). An FDE spends a large part of an
engagement on the data foundation: modelling, permissions, and getting clean data into the org.
Debugging in a client's org works the same way: form a hypothesis, test it with a small
diagnostic instead of guessing, and look for the root cause behind the noisy error. Security
constraints such as token redaction are not obstacles to work around; the design should respect
them.

### Possible interview questions
- *Why extend standard objects (Order, Case, Opportunity) instead of building custom objects?*
- *You deployed a new field but nobody can see it. What is the cause, and how do you fix it properly?*
- *Why use permission sets instead of editing profiles?*
- *In what order do you load related data into Salesforce, and why?*
- *Why separate data generation from data loading?*
- *A bulk insert returns hundreds of errors. How do you find the real one?*
- *Your first hypothesis about a bug was wrong. How did you find out, and what did you do next?*
- *How does your Python code authenticate to Salesforce without handling secrets?*
- *How do you validate data before loading it into a client's org?*
- *How will the agent's permissions limit what data it can see?*

---

<!-- Next steps are added as the project continues. -->
