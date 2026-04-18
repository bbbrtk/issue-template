"""
Reads config/*.txt files and updates dropdown/checkbox options
in all .github/ISSUE_TEMPLATE/*.yml files.
"""

import sys
from pathlib import Path
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
TEMPLATES_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"

DROPDOWN_MAP = {
    "environment": CONFIG_DIR / "environments.txt",
    "profile": CONFIG_DIR / "profiles.txt",
}
CHECKBOX_MAP = {
    "permission_set_groups": CONFIG_DIR / "permission_set_groups.txt",
}


def load_config(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def update_template(template_path: Path, dropdowns: dict, checkboxes: dict) -> bool:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096

    data = yaml.load(template_path)
    changed = False

    for field in data.get("body", []):
        field_id = field.get("id", "")
        field_type = field.get("type", "")

        if field_type == "dropdown" and field_id in dropdowns:
            new_options = dropdowns[field_id]
            if list(field["attributes"]["options"]) != new_options:
                field["attributes"]["options"] = new_options
                changed = True

        elif field_type == "checkboxes" and field_id in checkboxes:
            new_options = [{"label": v} for v in checkboxes[field_id]]
            current = [dict(o) for o in field["attributes"]["options"]]
            if current != new_options:
                field["attributes"]["options"] = new_options
                changed = True

    if changed:
        with template_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f)
        print(f"  Updated: {template_path.name}")
    else:
        print(f"  No changes: {template_path.name}")

    return changed


def main():
    dropdowns = {fid: load_config(path) for fid, path in DROPDOWN_MAP.items()}
    checkboxes = {fid: load_config(path) for fid, path in CHECKBOX_MAP.items()}

    templates = sorted(TEMPLATES_DIR.glob("*.yml"))
    if not templates:
        print("No issue templates found.", file=sys.stderr)
        sys.exit(1)

    any_changed = False
    for template in templates:
        any_changed |= update_template(template, dropdowns, checkboxes)

    sys.exit(0 if any_changed else 2)


if __name__ == "__main__":
    main()
