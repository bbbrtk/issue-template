# Salesforce User Management Automation

GitHub-based self-service portal for managing Salesforce users across multiple environments. Requesters open a GitHub Issue; automation handles the rest.

---

## How it works

```
Requester opens Issue (creation / deletion / update)
  │
  ├─► Teams notification sent immediately
  │
  └─► Issue closed (approved)
        │
        ├─► CSV updated  →  PR opened against main
        │
        └─► PR merged to main
              │
              └─► Apex executed against target Salesforce org
```

---

## Repository structure

```
.github/
  ISSUE_TEMPLATE/
    user-creation.yml       # Issue form: new user request
    user-deletion.yml       # Issue form: deactivation request
    user-update.yml         # Issue form: profile / PSG change request
  workflows/
    notify-teams.yml        # Sends Teams message when issue is opened
    process-issue.yml       # Parses closed issue → opens CSV PR
    sync-users.yml          # On CSV change merged to main → runs Apex
    update-issue-templates.yml  # Keeps dropdown options in sync with config/

apex/
  create_user.apex          # Anonymous Apex: create user + assign PSGs
  deactivate_user.apex      # Anonymous Apex: set IsActive = false
  update_user.apex          # Anonymous Apex: update profile + PSGs

config/
  environments.txt          # Source of truth for Environment dropdown
  profiles.txt              # Source of truth for Profile dropdown
  permission_set_groups.txt # Source of truth for PSG checkboxes

scripts/
  update_templates.py       # Rewrites dropdown options in issue templates
  process_issue.py          # Parses issue body → modifies CSV
  detect_changes.py         # Diffs CSVs HEAD~1 vs HEAD → operations.json
  generate_apex.py          # Substitutes placeholders in Apex templates

users/salesforce/
  prod.csv                  # One file per environment — source of truth
  preprod.csv
  uat.csv
  ... (one per environment)
```

---

## Setup

### 1. Configure dropdown options

Edit the plain-text files in `config/` — one value per line, `#` for comments:

| File | Controls |
|---|---|
| `config/environments.txt` | Environment dropdown in all three issue forms |
| `config/profiles.txt` | Profile dropdown |
| `config/permission_set_groups.txt` | Permission Set Group checkboxes |

Push changes to `main`. The **Update Issue Templates** workflow runs automatically and rewrites the dropdown options in `.github/ISSUE_TEMPLATE/*.yml`.

---

### 2. Configure GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and create the following secrets.

#### `TEAMS_WEBHOOK_URL`

The Incoming Webhook URL for your Microsoft Teams channel.

1. In Teams: open the channel → **⋯ → Connectors → Incoming Webhook → Configure**
2. Copy the generated URL
3. Add it as the `TEAMS_WEBHOOK_URL` secret

#### `SF_AUTH_URLS`

A JSON object mapping each environment name (must match `config/environments.txt`, uppercased) to its SFDX auth URL.

**Format:**
```json
{
  "PROD":    "force://PlatformCLI::5Aep861bB...@company.my.salesforce.com",
  "PREPROD": "force://PlatformCLI::5Aep861bB...@company--preprod.sandbox.my.salesforce.com",
  "UAT":     "force://PlatformCLI::5Aep861bB...@company--uat.sandbox.my.salesforce.com"
}
```

**How to get an SFDX auth URL for each org:**

```bash
# Authenticate interactively (once per org)
sf org login web --alias my-org

# Retrieve the auth URL
sf org display --target-org my-org --verbose --json \
  | jq -r '.result.sfdxAuthUrl'
```

Repeat for every environment and build the JSON object above. Paste the full JSON as the value of the `SF_AUTH_URLS` secret.

> Environments absent from the JSON will be skipped with a warning rather than failing the workflow.

---

### 3. Grant workflow permissions

Go to **Settings → Actions → General → Workflow permissions** and set:

- **Read and write permissions** ✓
- **Allow GitHub Actions to create and approve pull requests** ✓

---

### 4. Seed the CSV files

The files under `users/salesforce/` are the source of truth for each org. Each file maps to one environment (filename = environment name lowercased, spaces replaced with `_`).

Columns:

| Column | Description |
|---|---|
| `first_name` | User's first name |
| `last_name` | User's last name |
| `email` | Email address (used as the unique key) |
| `profile` | Salesforce profile name (must exist in the org) |
| `permission_set_groups` | Pipe-separated PSG labels, e.g. `Sales Operations\|IT Administration` |
| `is_active` | `true` / `false` |

Make sure the existing org users are reflected in these files before enabling the sync workflow, to avoid accidental duplicate creation.

---

## Day-to-day usage

### Requesting a user change

1. Open a new Issue on this repository
2. Select the appropriate template: **User Creation**, **User Deletion**, or **User Update**
3. Fill in the form and submit

A Teams notification is sent to the channel immediately.

### Approving and applying the change

1. Review the issue; close it when approved
2. The **Process Issue** workflow opens a PR with the CSV change
3. Review and merge the PR
4. The **Sync Users** workflow runs Apex against the target org automatically

### Updating dropdown options

Edit the relevant file in `config/` and push to `main`. The issue templates update within ~1 minute.

### Adding a new environment

1. Add the environment name to `config/environments.txt` and push to `main`
2. Create `users/salesforce/<env_lowercased>.csv` with the header row
3. Add the environment's SFDX auth URL to the `SF_AUTH_URLS` secret

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Teams notification not sent | Verify `TEAMS_WEBHOOK_URL` secret is set; check the **Notify Teams** workflow run logs |
| CSV PR not opened after issue close | Confirm issue has a `user-management` label; check **Process Issue** run logs |
| Sync workflow skips an environment | Ensure the environment key in `SF_AUTH_URLS` matches the CSV filename stem uppercased (e.g. `qa1data.csv` → `QA1DATA`) |
| Apex error: Profile not found | The profile name in the CSV must exactly match the `Name` field in Salesforce |
| Apex error: PSG not found or not ready | PSG `MasterLabel` must match exactly and its `Status` must be `Updated` in the target org |
| Auth URL expired | Re-run `sf org display --verbose --json` for the affected org and update `SF_AUTH_URLS` |
