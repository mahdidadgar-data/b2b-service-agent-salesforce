# Claude via Salesforce Hosted MCP: setup

How to reproduce the Step 7 setup: Claude (claude.ai) reads Delta's Salesforce data through a
**Salesforce Hosted MCP server** with two read-only tools. The tools are the same flows the
Agentforce agent uses, so the hard guardrails live in one place.

```
claude.ai Project "Delta Service Agent (Claude)"         (soft layer: project-instructions.md)
   │  custom connector, OAuth 2.0 + PKCE, as "Delta MCP User"
   ▼
Salesforce Hosted MCP server "Delta Service Tools"        (tool descriptions + read-only annotations)
   https://api.salesforce.com/platform/mcp/v1/d/<my-domain>/develop/custom/DeltaServiceTools
   │  get_order_status   → flow Get_Order_Status  (v2)
   │  get_product_specs  → flow Get_Product_Specs (v4)
   ▼
Flows run in the MCP user's context                       (hard layer: ownership check, active
   Delta_MCP_Base + Delta_MCP_Data_Read                     products only, explicit outputs, no prices)
```

No secrets, usernames or the real My Domain are in this repo. Replace `<my-domain>`,
`<mcp-username>` and `<CONSUMER_KEY>` with your own values locally.

## What is in Git and what is manual

| Component | In Git | How it gets into an org |
|---|---|---|
| Permission sets `Delta_MCP_Base`, `Delta_MCP_Data_Read` | `force-app/main/default/permissionsets/` | Deploy (step 1) |
| User "Delta MCP User" | No (a user record, not metadata) | Manual (step 2) |
| MCP server `DeltaServiceTools` | `force-app/main/default/mcpServerDefinitions/` | Built in Setup, retrieved; deployable (step 3) |
| External Client App `Claude_MCP_Client`: policies | `force-app/main/default/extlClntApp*Policies/`, `extlClntAppOauthSecuritySettings/` | Built in Setup (step 4); these 3 files only deploy where the app exists |
| External Client App: header, global OAuth settings, OAuth settings | **Templates only**: `docs/claude-mcp/eca-templates/*.example` | Manual (step 4). Real files are in `.forceignore` and `.gitignore` |
| claude.ai connector and Project | No (lives in claude.ai) | Manual (steps 5–6); instructions in [project-instructions.md](project-instructions.md) |

## Prerequisites
- The flows `Get_Order_Status` (v2) and `Get_Product_Specs` (v4) are active (Steps 4 and 6b).
- Setup → MCP Servers is available (Developer Edition with Agentforce). Setup shows a banner that
  Salesforce MCP server usage may be billed (Flex Credits); check this before using it in a real org.

## Step 1: permission sets

```powershell
sf project deploy start --target-org delta-dev `
  --source-dir force-app/main/default/permissionsets/Delta_MCP_Base.permissionset-meta.xml `
  --source-dir force-app/main/default/permissionsets/Delta_MCP_Data_Read.permissionset-meta.xml
```

| Permission set | Contents | Why |
|---|---|---|
| `Delta_MCP_Base` | User permissions **API Enabled** and **Run Flows**, nothing else | The platform minimum to call a flow over MCP. The External Client App only admits users with this set (step 4), so it doubles as the "may use Claude" switch |
| `Delta_MCP_Data_Read` | **Read** on Account, Order, Product2; read-only FLS on the 16 fields the two flows read (incl. `Order.Name` and `Product2.ProductCode`) | Exactly the data the two flows need, nothing more. No Case or Opportunity, so the write flows fail for this user even though Run Flows lets it start them |

- **Why two sets instead of one:** with only `Delta_MCP_Base` assigned, a tool call must fail if
  the flow runs in the user's context. That is the run-context proof (learning log, Step 7 test 1).
- **Never add Edit to `Delta_MCP_Data_Read`.** Account and Order sharing is Public Read/Write, so
  the object permission is the only thing that keeps this user read-only.
- **Run Flows is broad** (any active autolaunched flow). Restricting flow access per flow is on
  the Step 8 list.

## Step 2: the MCP user

Setup → Users → New User:
- **License:** Salesforce. **Profile:** Minimum Access - Salesforce.
- Username and email: your own choice. **Do not put them in the repo.**
- Assign the two permission sets:

```powershell
sf org assign permset --target-org delta-dev --name Delta_MCP_Base --on-behalf-of <mcp-username>
sf org assign permset --target-org delta-dev --name Delta_MCP_Data_Read --on-behalf-of <mcp-username>
```

Why:
- **A dedicated user, not the admin.** Claude's tool calls run as this user, so its permissions are
  the ceiling of what Claude can reach. Connecting as the admin would make the guardrails meaningless.
- **Minimum Access - Salesforce** grants nothing on Account, Order or Product2 (verified with
  `ObjectPermissions` and `FieldPermissions` queries). The profile is the floor, and here the floor
  is zero, unlike the Einstein Agent User profile (Step 6c: FLS on `Amount`).
- **Not the Salesforce Integration licence:** its profile is API-only, which doesn't fit an
  interactive OAuth login from claude.ai.

## Step 3: the hosted MCP server

Setup → Integrations → API Catalog → **MCP Servers**.

1. **Leave all standard servers inactive** (15 in this org, e.g. "SObject All", "SObject
   Mutations"). Why: they expose generic create/read/update on many objects. Test 4 showed that
   Claude, without instructions, suggests connecting a general Salesforce connector for a
   cross-customer query; that is only harmless because nothing general is active.
2. **Add MCP Server → custom:** name "Delta Service Tools", API name `DeltaServiceTools`.
3. **Add Server Assets → tools:** the flows `Get_Order_Status` and `Get_Product_Specs` from the API
   Catalog. Tool names `get_order_status` and `get_product_specs`.
4. **Per tool:** annotations **Read-only** and **Idempotent** (not destructive, not open-world), and
   a description written for Claude (when to call it, never guess inputs, what an empty value or
   `orderFound = false` means, no prices). The full text is in the metadata file.
5. **Activate** the server.

The server definition is in Git:
`force-app/main/default/mcpServerDefinitions/DeltaServiceTools.mcpServerDefinition-meta.xml`.

```powershell
sf project deploy start --target-org delta-dev --metadata McpServerDefinition:DeltaServiceTools
```

Validated on 13 Nov 2026 with `--dry-run`: succeeded, state **Unchanged**, so the file in Git is
valid source format and identical to the server that is active in the org.

Why the annotations and descriptions matter: the annotations tell the client these tools are safe
to repeat and change nothing; claude.ai groups them as "Read-only tools". The descriptions are the
only thing Claude knows about a tool, so they carry the same rules as the Agentforce action
descriptions.

## Step 4: the External Client App (OAuth client for Claude)

Setup → External Client App Manager → New External Client App, name "Claude MCP Client"
(`Claude_MCP_Client`), distribution **Local**.

| Setting | Value | Why |
|---|---|---|
| OAuth scopes | **Access Salesforce hosted MCP servers (`mcp_api`)** + **refresh token / offline access**. Not `api`, not `full` | The token can call the MCP server and nothing else: no REST or SOQL access with the same token |
| Callback URLs | `https://claude.ai/api/mcp/auth_callback` and `http://localhost:38000/callback` | claude.ai's connector callback, plus a local callback for a desktop/CLI client. Nothing else can receive a code |
| PKCE | Required | Protects the authorization code without a client secret |
| Consumer secret | Not required | A public client (claude.ai with your own OAuth client ID); PKCE replaces the secret, so there is no secret to leak |
| Other flows | Client credentials, device flow, token exchange: **off** | Only the interactive authorization-code flow, so a person must log in as the MCP user |
| Refresh tokens | **Rotation on**; valid until **30 days of inactivity**, enforced | A stolen refresh token is single-use and expires when the connector is not used |
| Access tokens | JWT-based for named users: on | Short-lived, verifiable tokens tied to the user |
| Permitted users | **Admin approved users are pre-authorized**, permission set **`Delta_MCP_Base` only** | Even a valid login fails for any user without the base set; removing the set revokes Claude's access |
| IP relaxation | Enforce | The org's IP restrictions apply to the app |

**The retrieved metadata confirms these settings from the org itself** (not only from the UI):
`commaSeparatedOauthScopes = RefreshToken, MCP`, `isPkceRequired = true`,
`isRefreshTokenRotationEnabled = true`, `isEnforceRefreshTokenTTL = true` with
`refreshTokenPolicyType = SpecificInactivity` / `30 Days`,
`permittedUsersPolicyType = AdminApprovedPreAuthorized` with
`commaSeparatedPermissionSet = Delta_MCP_Base`, client credentials / device / token exchange
`false`, `isConsumerSecretOptional = true`.

**Why three ECA files are templates instead of source:**

| File | Reason |
|---|---|
| `Claude_MCP_Client.eca` (ExternalClientApplication) | Contains the admin's **contact email** and the org ID |
| `Claude_MCP_Client_glbloauth.ecaGlblOauth` (ExtlClntAppGlobalOauthSettings) | Contains the **consumer key** |
| `Claude_MCP_Client_oauth.ecaOauth` (ExtlClntAppOauthSettings) | No secret, but `oauthLink` holds **org-specific IDs**, so it fits only this org |

The redacted versions are in [eca-templates/](eca-templates/) with `<CONSUMER_KEY>`,
`<CONTACT_EMAIL>`, `<ORG_ID>` and `<OAUTH_LINK_ID>` placeholders. The real files are excluded in
`.forceignore` (the CLI never writes them into `force-app`) and `.gitignore` (a manual copy can't be
committed). The retrieve was done into a temporary folder outside the project, scanned, and only
the clean files were copied into `force-app`.

The **consumer key** is shown in the app's OAuth settings in Setup. You need it once, for step 5.
Never paste it into a file in this repo.

## Step 5: the claude.ai connector

claude.ai → Settings → Connectors → **Add custom connector**:
- URL: `https://api.salesforce.com/platform/mcp/v1/d/<my-domain>/develop/custom/DeltaServiceTools`
- Advanced → **Use your own OAuth client**: client ID = the consumer key. No secret.
- Connect, log in to Salesforce **as the Delta MCP User** (not as the admin), and allow access.

Tool permissions: the two tools appear under "Read-only tools". Set them to "Needs approval" or
"Always allow" as you prefer. **Note:** in Auto mode, Claude may run tools without asking even when
they are set to "Needs approval" (claude.ai says so on the connector page). That is acceptable for
read-only tools and is the reason **no write tools are exposed over MCP**: complaints and quote
requests stay in Agentforce, where the confirmation is a platform gate.

## Step 6: the Claude Project

claude.ai → Projects → New project "Delta Service Agent (Claude)":
- Paste the instructions from [project-instructions.md](project-instructions.md).
- Use the "Delta Service Tools" connector in the Project's conversations.

Why a Project: without instructions, Claude is a general assistant that tries to be helpful, for
example by suggesting another connector and writing a cross-customer SOQL query (test 4). The
Project instructions turn it into Delta's service assistant with the same rules as the Agentforce
agent (test 5).

## Step 7: verify

The tests and their results are in the learning log, **Step 7**. The two that prove the setup:
1. **Run context:** assign only `Delta_MCP_Base` and ask for an order. The tool call must fail
   (`INVALID_TYPE`: the user can't see Account). Then add `Delta_MCP_Data_Read`: the same question
   gives the order status.
2. **Ownership:** a different customer number with the same order number gives the identical
   "no order found" message.

To switch Claude's access off: deactivate the MCP server, or remove `Delta_MCP_Base` from the user
(the External Client App then refuses the user), or revoke the user's OAuth token in Setup.
