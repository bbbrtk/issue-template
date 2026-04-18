"""
Parses a closed GitHub Issue (user-creation / user-deletion / user-update)
and applies the change to the matching environment CSV file.

Reads from environment variables:
  ISSUE_BODY, ISSUE_LABELS

Writes key values to $GITHUB_OUTPUT for use in subsequent workflow steps.

Exit codes:
  0 – CSV modified successfully
  1 – error
"""

import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USERS_DIR = ROOT / "users" / "salesforce"

CSV_COLUMNS = ["first_name", "last_name", "email", "profile", "permission_set_groups", "is_active"]

ENV_FILE_MAP = {
    "prod":      "prod.csv",
    "preprod":   "preprod.csv",
    "uat":       "uat.csv",
    "tsit":      "tsit.csv",
    "sit":       "sit.csv",
    "qa1":       "qa1.csv",
    "qa1data":   "qa1data.csv",
    "qa2":       "qa2.csv",
    "qa2data":   "qa2data.csv",
    "dev008":    "dev008.csv",
    "dev010":    "dev010.csv",
    "dev011":    "dev011.csv",
    "dev012":    "dev012.csv",
    "dev012data":"dev012data.csv",
    "dev013":    "dev013.csv",
    "dev014":    "dev014.csv",
    "dev015":    "dev015.csv",
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_issue_body(body: str) -> dict:
    """Split a GitHub issue form body into {field_label: raw_value}."""
    result = {}
    parts = re.split(r"^### ", body, flags=re.MULTILINE)
    for part in parts:
        if not part.strip():
            continue
        lines = part.splitlines()
        field = lines[0].strip()
        value_lines = [l for l in lines[1:] if l.strip()]
        value = "\n".join(value_lines).strip()
        result[field] = "" if value == "_No response_" else value
    return result


def parse_checkboxes(text: str) -> list[str]:
    """Return labels of checked checkboxes."""
    return re.findall(r"- \[[xX]\] (.+)", text)


def determine_operation(labels: str) -> str:
    if "user-creation" in labels:
        return "creation"
    if "user-deletion" in labels:
        return "deletion"
    if "user-update" in labels:
        return "update"
    return ""


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def csv_path(env: str) -> Path:
    key = env.strip().lower()
    filename = ENV_FILE_MAP.get(key)
    if not filename:
        print(f"ERROR: Unknown environment '{env}'", file=sys.stderr)
        sys.exit(1)
    return USERS_DIR / filename


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def op_creation(rows: list[dict], record: dict) -> list[dict]:
    email = record["email"]
    if any(r["email"].lower() == email for r in rows):
        print(f"ERROR: User '{email}' already exists in this environment.", file=sys.stderr)
        sys.exit(1)
    rows.append({**record, "is_active": "true"})
    return rows


def op_deletion(rows: list[dict], email: str) -> list[dict]:
    matched = [r for r in rows if r["email"].lower() == email]
    if not matched:
        print(f"ERROR: User '{email}' not found.", file=sys.stderr)
        sys.exit(1)
    for r in rows:
        if r["email"].lower() == email:
            r["is_active"] = "false"
    return rows


def op_update(rows: list[dict], record: dict) -> list[dict]:
    email = record["email"]
    matched = [r for r in rows if r["email"].lower() == email]
    if not matched:
        print(f"ERROR: User '{email}' not found.", file=sys.stderr)
        sys.exit(1)
    for r in rows:
        if r["email"].lower() == email:
            for field in ("first_name", "last_name", "profile", "permission_set_groups"):
                if record.get(field):
                    r[field] = record[field]
    return rows


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def set_github_output(**kwargs) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as f:
        for key, value in kwargs.items():
            # Sanitise: strip newlines so the key=value format stays valid
            f.write(f"{key}={str(value).strip()}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    body   = os.environ.get("ISSUE_BODY", "")
    labels = os.environ.get("ISSUE_LABELS", "")

    operation = determine_operation(labels)
    if not operation:
        print("No user-management operation label found — skipping.", file=sys.stderr)
        sys.exit(1)

    fields = parse_issue_body(body)

    first_name  = fields.get("First Name", "").strip()
    last_name   = fields.get("Last Name", "").strip()
    email       = fields.get("Email", "").strip().lower()
    profile     = fields.get("Profile", "").strip()
    environment = fields.get("Environment", "").strip()
    psgs        = "|".join(parse_checkboxes(fields.get("Permission Set Groups", "")))

    if not email:
        print("ERROR: Email field is empty.", file=sys.stderr)
        sys.exit(1)
    if not environment:
        print("ERROR: Environment field is empty.", file=sys.stderr)
        sys.exit(1)

    target = csv_path(environment)
    rows   = read_csv(target)

    record = {
        "first_name":           first_name,
        "last_name":            last_name,
        "email":                email,
        "profile":              profile,
        "permission_set_groups": psgs,
    }

    if operation == "creation":
        rows = op_creation(rows, record)
    elif operation == "deletion":
        rows = op_deletion(rows, email)
    elif operation == "update":
        rows = op_update(rows, record)

    write_csv(target, rows)

    print(f"OK: applied '{operation}' for {email} → {target.name}")

    set_github_output(
        operation=operation,
        email=email,
        first_name=first_name,
        last_name=last_name,
        environment=environment,
        csv_file=target.name,
    )


if __name__ == "__main__":
    main()
