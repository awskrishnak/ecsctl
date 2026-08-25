import json
import yaml
from typing import Any


class OutputFormatter:
    SUPPORTED = ["table", "json", "yaml"]

    def __init__(self, format_type: str = "table"):
        self.format_type = format_type.lower()

    def print(self, data: Any):
        if self.format_type == "json":
            print(json.dumps(data, indent=2, default=str))
        elif self.format_type == "yaml":
            print(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))
        else:
            self._print_table(data)

    def dumps(self, data: Any) -> str:
        if self.format_type == "json":
            return json.dumps(data, indent=2, default=str)
        elif self.format_type == "yaml":
            return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        else:
            return str(data)

    def _print_table(self, data: Any):
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[_truncate(str(row.get(h, "")), 60) for h in headers] for row in data]
            _print_plain_table(headers, rows)
        elif isinstance(data, dict):
            rows = [[k, _truncate(str(v), 80)] for k, v in data.items()]
            _print_plain_table(["KEY", "VALUE"], rows)
        else:
            print(data)


def _truncate(s, max_len):
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s


def _print_plain_table(headers, rows):
    """kubectl-style plain table: UPPERCASE headers, space-padded columns, no borders."""
    upper_headers = [h.upper() for h in headers]
    col_widths = [len(h) for h in upper_headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(upper_headers))
    print(header_line)

    for row in rows:
        line = "  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        print(line)


def print_describe(data, indent=0):
    """kubectl-describe style output: Key: Value with nested indentation."""
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{prefix}{key}:")
                print_describe(value, indent + 1)
            elif isinstance(value, list):
                if not value:
                    print(f"{prefix}{key}:  <none>")
                elif all(isinstance(v, (str, int, float, bool)) for v in value):
                    print(f"{prefix}{key}:  {', '.join(str(v) for v in value)}")
                elif all(isinstance(v, dict) for v in value):
                    print(f"{prefix}{key}:")
                    for item in value:
                        _print_list_item(item, indent + 1)
                else:
                    print(f"{prefix}{key}:  {value}")
            else:
                print(f"{prefix}{key}:\t{value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _print_list_item(item, indent)
            else:
                print(f"{prefix}- {item}")


def _print_list_item(item, indent):
    """Print a dict as a list item with dash prefix on first line."""
    prefix = "  " * indent
    lines = []
    for k, v in item.items():
        if isinstance(v, (dict, list)):
            lines.append((k, v, True))
        else:
            lines.append((k, v, False))

    first = True
    for k, v, is_complex in lines:
        if first:
            marker = "- "
            first = False
        else:
            marker = "  "
        if is_complex:
            print(f"{prefix}{marker}{k}:")
            print_describe(v, indent + 2)
        else:
            print(f"{prefix}{marker}{k}: {v}")
