import json
from typing import Dict, Any
import boto3
import click


class AWSExecutor:
    """AWS API executor with dry-run support."""

    def __init__(self, dry_run: bool = False, session=None):
        self.dry_run = dry_run
        self._session = session or boto3.Session()
        self._clients = {}
        self.logs = []

    @property
    def clients(self):
        return self._clients

    def client(self, service: str):
        if service not in self._clients:
            self._clients[service] = self._session.client(service)
        return self._clients[service]

    def call(self, service: str, action: str, params: Dict[str, Any]) -> Any:
        client = self.client(service)
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
