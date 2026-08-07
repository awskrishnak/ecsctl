import json
from typing import Dict, Any
import boto3


class AWSExecutor:
    """AWS API executor with dry-run support."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.clients = {
            "ecs": boto3.client("ecs"),
            "autoscaling": boto3.client("autoscaling"),
            "elbv2": boto3.client("elbv2"),
            "servicediscovery": boto3.client("servicediscovery"),
            "acm": boto3.client("acm"),
            "iam": boto3.client("iam"),
        }
        self.logs = []

    def call(self, service: str, action: str, params: Dict[str, Any]) -> Any:
        client = self.clients[service]
        method = getattr(client, action)
        if self.dry_run:
            log_entry = {
                "service": service,
                "action": action,
                "params": params,
            }
            self.logs.append(log_entry)
            click.echo(f"[DRY-RUN] {service}.{action}")
            return {"DryRun": True, "action": action, "service": service}
        return method(**params)

    def flush_logs(self):
        if self.dry_run and self.logs:
            click.echo("\n--- Dry Run Summary ---")
            for log in self.logs:
                click.echo(json.dumps(log, indent=2, default=str))


import click
