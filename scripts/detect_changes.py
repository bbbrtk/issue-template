"""
Compares HEAD vs HEAD~1 for any changed CSV files under users/salesforce/,
classifies each row change as create / update / deactivate, and writes
operations.json to the repo root.

Exit codes:
  0 – one or more operations written
  2 – no changes detected (nothing to sync)
  1 – error
"""

import csv
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(*args) -> str:
    result = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def file_at(commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def changed_csv_files() -> list[str]:
    raw = git("diff", "--name-only", "HEAD~1", "HEAD", "--", "users/salesforce/")
    return [f.strip() for f in raw.splitlines() if f.strip().endswith(".csv")]


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def parse_rows(content: str | None) -> dict[str, dict]:
    if not content:
        return {}
    reader = csv.DictReader(io.StringIO(content))
    return {row["email"].strip().lower(): row for row in reader if row.get("email")}


def env_from_path(path: str) -> str:
    """users/salesforce/prod.csv  →  PROD"""
    return Path(path).stem.upper()


# ---------------------------------------------------------------------------
# Username / alias derivation
# ---------------------------------------------------------------------------

def build_username(email: str, env: str) -> str:
    local, domain = email.split("@", 1)
    return f"{local}.{env.lower()}@{domain}"


def compute_alias(first: str, last: str) -> str:
    clean = lambda s: re.sub(r"[^a-zA-Z0-9]", "", s).lower()
    return (clean(first)[:1] + clean(last)[:7])[:8] or "user"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    files = changed_csv_files()
    if not files:
        print("No CSV files changed under users/salesforce/ — nothing to sync.", file=sys.stderr)
        sys.exit(2)

    operations: list[dict] = []

    for filepath in files:
        env      = env_from_path(filepath)
        old_rows = parse_rows(file_at("HEAD~1", filepath))
        new_rows = parse_rows(file_at("HEAD",   filepath))

        # ── CREATE: email appears in new, not in old (and is_active = true) ──
        for email, row in new_rows.items():
            if email not in old_rows and row.get("is_active", "true").lower() == "true":
                operations.append({
                    "operation":             "create",
                    "environment":           env,
                    "first_name":            row.get("first_name", ""),
                    "last_name":             row.get("last_name",  ""),
                    "email":                 email,
                    "username":              build_username(email, env),
                    "alias":                 compute_alias(row.get("first_name", ""), row.get("last_name", "")),
                    "profile":               row.get("profile", ""),
                    "permission_set_groups": row.get("permission_set_groups", ""),
                })

        # ── DEACTIVATE: removed row, or is_active flipped false ──────────────
        for email, old_row in old_rows.items():
            if email not in new_rows:
                operations.append({"operation": "deactivate", "environment": env, "email": email})
            elif (old_row.get("is_active", "true").lower() == "true"
                  and new_rows[email].get("is_active", "true").lower() == "false"):
                operations.append({"operation": "deactivate", "environment": env, "email": email})

        # ── UPDATE: email in both, active, data changed ───────────────────────
        watched = {"first_name", "last_name", "profile", "permission_set_groups"}
        for email, new_row in new_rows.items():
            if email not in old_rows:
                continue
            if new_row.get("is_active", "true").lower() != "true":
                continue
            if any(old_rows[email].get(f) != new_row.get(f) for f in watched):
                operations.append({
                    "operation":             "update",
                    "environment":           env,
                    "first_name":            new_row.get("first_name", ""),
                    "last_name":             new_row.get("last_name",  ""),
                    "email":                 email,
                    "profile":               new_row.get("profile", ""),
                    "permission_set_groups": new_row.get("permission_set_groups", ""),
                })

    out = ROOT / "operations.json"
    out.write_text(json.dumps(operations, indent=2))
    print(f"Detected {len(operations)} operation(s) → {out}")
    sys.exit(0 if operations else 2)


if __name__ == "__main__":
    main()
