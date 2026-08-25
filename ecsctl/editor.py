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
from ecsctl.diff import calculate_diff, print_diff


def edit_resource(resource_type: str, name: str, cluster: str, editor: str, dry_run: bool, session=None):
    formatter = OutputFormatter("yaml")
    resource = fetch_resource(resource_type, name, cluster, session=session)
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
            executor = AWSExecutor(dry_run=dry_run, session=session)
            result = apply_resource(edited_resource, executor, cluster)
            if dry_run:
                executor.flush_logs()
            else:
                click.echo(f"Applied: {result}")
        else:
            click.echo("Aborted.")
    finally:
        os.unlink(tmp_path)
