"""
Reads an Apex template from apex/<operation>_user.apex, substitutes
%%PLACEHOLDER%% markers with values from a JSON operation dict, and
prints the resulting script to stdout.

Usage:
  python scripts/generate_apex.py <operation> <json_operation_string>

Example:
  python scripts/generate_apex.py create '{"email":"j@x.com","profile":"Standard User",...}'
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def escape_apex(value: str) -> str:
    """Escape single quotes for Apex string literals."""
    return str(value).replace("'", "\\'")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: generate_apex.py <operation> <json>", file=sys.stderr)
        sys.exit(1)

    operation = sys.argv[1]
    op        = json.loads(sys.argv[2])

    template_path = ROOT / "apex" / f"{operation}_user.apex"
    if not template_path.exists():
        print(f"ERROR: template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    template = template_path.read_text(encoding="utf-8")

    substitutions = {
        "%%FIRST_NAME%%":           escape_apex(op.get("first_name",            "")),
        "%%LAST_NAME%%":            escape_apex(op.get("last_name",             "")),
        "%%EMAIL%%":                escape_apex(op.get("email",                 "")),
        "%%USERNAME%%":             escape_apex(op.get("username",              "")),
        "%%ALIAS%%":                escape_apex(op.get("alias",                 "")),
        "%%PROFILE%%":              escape_apex(op.get("profile",               "")),
        "%%PERMISSION_SET_GROUPS%%": escape_apex(op.get("permission_set_groups", "")),
    }

    for placeholder, value in substitutions.items():
        template = template.replace(placeholder, value)

    print(template)


if __name__ == "__main__":
    main()
