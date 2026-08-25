import time
import click
from ecsctl.output import OutputFormatter


@click.command()
@click.argument("resource_type")
@click.argument("name")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("-o", "--output", default="table", type=click.Choice(["table", "json", "yaml"]))
@click.option("--limit", type=int, default=20, help="Number of events to show")
@click.option("-w", "--watch", is_flag=True, help="Watch for new events")
@click.pass_context
def events(ctx, resource_type, name, cluster, output, limit, watch):
    """Show events for a resource.

    Example: ecsctl events service my-app
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    session = config.get_session()
    ecs = session.client("ecs")
    formatter = OutputFormatter(output)

    from ecsctl.types import normalize_resource_type
    resource_type = normalize_resource_type(resource_type)

    if resource_type != "service":
        raise click.ClickException(f"Events not supported for {resource_type}. Supported: service")

    seen_ids = set()

    try:
        while True:
            resp = ecs.describe_services(cluster=cluster, services=[name])
            services = resp.get("services", [])
            if not services:
                raise click.ClickException(f"Service {name} not found")

            service_events = services[0].get("events", [])[:limit]

            if watch:
                new_events = [e for e in service_events if e["id"] not in seen_ids]
                for event in reversed(new_events):
                    seen_ids.add(event["id"])
                    _print_event(event, formatter, output)
                time.sleep(5)
            else:
                data = [{
                    "timestamp": str(e["createdAt"]),
                    "message": e["message"],
                } for e in service_events]
                formatter.print(data)
                break
    except KeyboardInterrupt:
        pass


def _print_event(event, formatter, output):
    if output == "table":
        ts = str(event["createdAt"])
        msg = event["message"]
        click.echo(f"{ts}  {msg}")
    else:
        formatter.print({"timestamp": str(event["createdAt"]), "message": event["message"]})
