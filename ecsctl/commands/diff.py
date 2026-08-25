import os
import sys
import click
from ecsctl.resources.base import ECSResource
from ecsctl.fetcher import fetch_resource
from ecsctl.diff import calculate_diff, print_diff


@click.command(name="diff")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("-f", "--filename", multiple=True, required=True, help="YAML files to diff against live")
@click.pass_context
def diff_cmd(ctx, cluster, filename):
    """Show differences between local YAML and live resources.

    Exit code 0 if no diff, 1 if differences exist.

    Example: ecsctl diff -f service.yaml
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    session = config.get_session()

    has_diff = False

    for f in filename:
        if not os.path.exists(f):
            click.echo(f"File not found: {f}")
            continue

        resource = ECSResource.from_yaml(f)
        kind = resource.kind.lower().replace("-", "").replace("_", "")
        name = resource.metadata.name
        target_cluster = resource.metadata.namespace or cluster

        try:
            live = fetch_resource(kind, name, target_cluster, session=session)
        except ValueError as e:
            click.echo(f"  {resource.kind}/{name}: {e} (new resource)")
            has_diff = True
            continue
        except Exception as e:
            click.echo(f"  {resource.kind}/{name}: Error fetching live state: {e}")
            continue

        diff = calculate_diff(live, resource)
        if diff:
            has_diff = True
            click.echo(f"\n--- live {resource.kind}/{name}")
            click.echo(f"+++ local {f}")
            print_diff(diff, colored=True)
        else:
            click.echo(f"  {resource.kind}/{name}: no changes")

    if has_diff:
        sys.exit(1)
