import json
import click
from ecsctl.resources.base import ECSResource


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


def print_diff(diff: dict, colored=True):
    for key, change in diff.items():
        if isinstance(change, dict) and "old" in change and "new" in change:
            click.echo(f"  {key}:")
            old_str = json.dumps(change["old"], indent=4, default=str)
            new_str = json.dumps(change["new"], indent=4, default=str)
            if colored:
                click.echo(click.style(f"    - {old_str}", fg="red"))
                click.echo(click.style(f"    + {new_str}", fg="green"))
            else:
                click.echo(f"    - {old_str}")
                click.echo(f"    + {new_str}")
        elif key == "spec" and isinstance(change, dict):
            click.echo("  spec:")
            for sk, sc in change.items():
                click.echo(f"    {sk}:")
                old_str = json.dumps(sc["old"], indent=4, default=str)
                new_str = json.dumps(sc["new"], indent=4, default=str)
                if colored:
                    click.echo(click.style(f"      - {old_str}", fg="red"))
                    click.echo(click.style(f"      + {new_str}", fg="green"))
                else:
                    click.echo(f"      - {old_str}")
                    click.echo(f"      + {new_str}")
