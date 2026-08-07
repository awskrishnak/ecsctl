import os
import tempfile
import subprocess
import click
import yaml
from ecsctl.resources.base import ECSResource
from ecsctl.output import OutputFormatter
from ecsctl.fetcher import fetch_resource
from ecsctl.applier import apply_resource
from ecsctl.executor import AWSExecutor


def calculate_diff(old: ECSResource, new: ECSResource) -> dict:
    old_dict = old.to_dict()
    new_dict = new.to_dict()
    diff = {}
    for key in set(old_dict.keys()) | set(new_dict.keys()):
        if old_dict.get(key) != new_dict.get(key):
            diff[key] = {"old": old_dict.get(key), "new": new_dict.get(key)}
    old_spec = old_dict.get("spec", {})
    new_spec = new_dict.get("spec", {})
    spec_diff = {}
    for key in set(old_spec.keys()) | set(new_spec.keys()):
        if old_spec.get(key) != new_spec.get(key):
            spec_diff[key] = {"old": old_spec.get(key), "new": new_spec.get(key)}
    if spec_diff:
        diff["spec"] = spec_diff
    return diff


def print_diff(diff: dict):
    import json
    for key, change in diff.items():
        if isinstance(change, dict) and "old" in change and "new" in change:
            click.echo(f"  {key}:")
            click.echo(f"    - {json.dumps(change['old'], indent=4, default=str)}")
            click.echo(f"    + {json.dumps(change['new'], indent=4, default=str)}")
        elif key == "spec" and isinstance(change, dict):
            click.echo("  spec:")
            for sk, sc in change.items():
                click.echo(f"    {sk}:")
                click.echo(f"      - {json.dumps(sc['old'], indent=4, default=str)}")
                click.echo(f"      + {json.dumps(sc['new'], indent=4, default=str)}")


def edit_resource(resource_type: str, name: str, cluster: str, editor: str, dry_run: bool):
    formatter = OutputFormatter("yaml")
    resource = fetch_resource(resource_type, name, cluster)
    current_yaml = resource.to_yaml()

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False, encoding="utf-8") as tmp:
        tmp.write(current_yaml)
        tmp_path = tmp.name

    try:
        subprocess.call([editor, tmp_path])

        with open(tmp_path, "r", encoding="utf-8") as f:
            edited_data = yaml.safe_load(f)

        if not edited_data:
            click.echo("Empty file, aborting.")
            return

        edited_resource = ECSResource.from_dict(edited_data)

        if edited_resource.kind != resource.kind:
            click.echo(f"Error: Cannot change kind from {resource.kind} to {edited_resource.kind}")
            return
        if edited_resource.metadata.name != resource.metadata.name:
            click.echo(f"Error: Cannot change name from {resource.metadata.name} to {edited_resource.metadata.name}")
            return

        diff = calculate_diff(resource, edited_resource)
        if not diff:
            click.echo("No changes detected.")
            return

        click.echo("\nChanges to be applied:")
        print_diff(diff)
        click.echo("")

        if click.confirm("Apply changes?"):
            executor = AWSExecutor(dry_run=dry_run)
            result = apply_resource(edited_resource, executor, cluster)
            if dry_run:
                executor.flush_logs()
            else:
                click.echo(f"Applied: {result}")
        else:
            click.echo("Aborted.")
    finally:
        os.unlink(tmp_path)
