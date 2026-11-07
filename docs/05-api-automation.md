# Lab 5: PAN-OS XML API automation

**Goal:** automate a read-only security rule audit, then make a controlled change through the API.

## Rule audit (`pan_audit.py`)

- Dedicated `apiuser` with an admin role limited to XML API Report, Configuration and Operational Requests (no Commit, no Web UI, REST disabled).
- Reads the **running** rulebase (`action=show`) and flags: application any, service any, source and destination both any, disabled rules, logging off, no description.
- Writes `output/rule_audit_<timestamp>.csv` with zones, addresses and applications.

## Scripted change (`push_change.py`)

- Separate `apiwriter` account whose role adds **Commit**, created by `bootstrap-writer.ps1`: a one-time admin login (memory only) clones the existing read-only role and admin into the new ones, has the firewall hash the password, shows the plan, asks for confirmation, refuses to run if other changes are pending, and commits with a partial commit.
- **Dry run by default**; `--apply` stages the address object, then runs a **partial commit** scoped to that admin so other admins' pending changes are never committed.
- Polls the commit job, then verifies the object in the running config. `--remove` reverses it.

## Key handling

- Password typed once at a hidden prompt; never stored.
- API key stored encrypted with Windows DPAPI; decrypted into memory per run.
- `.secrets/`, `.venv/` and `output/` are git-ignored, and `publish.ps1` refuses to push if a secret file is tracked.

## Issue found and fixed

Key generation for the new local admin failed with `Invalid Credential`. The PA system log showed:

```text
auth-fail  failed authentication for user 'apiuser'. Reason: Authentication profile not found for the user.
```

The config was correct and committed. This matches a reported PAN-OS 11.1 issue on PA-400 series. Workaround: a Local Database authentication profile for the API admins (`admin-local`), assigned to the account.
