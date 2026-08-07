import json
import yaml
from typing import Any
from tabulate import tabulate


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
            rows = [[row.get(h, "") for h in headers] for row in data]
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        elif isinstance(data, dict):
            rows = [[k, v] for k, v in data.items()]
            print(tabulate(rows, headers=["Key", "Value"], tablefmt="grid"))
        else:
            print(data)
