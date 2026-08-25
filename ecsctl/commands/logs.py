import time
import click
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser
from ecsctl.streaming import stream_log_events


def parse_since(since_str):
    if not since_str:
        return None
    suffixes = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if since_str[-1] in suffixes and since_str[:-1].isdigit():
        delta = int(since_str[:-1]) * suffixes[since_str[-1]]
        return int((datetime.now(timezone.utc) - timedelta(seconds=delta)).timestamp() * 1000)
    dt = dateutil_parser.parse(since_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def resolve_log_config(ecs_client, cluster, target):
    """Resolve target to log group, stream prefix, and container name."""
    if "/" in target:
        resource_type, name = target.split("/", 1)
    else:
        resource_type, name = "service", target

    if resource_type == "service":
        resp = ecs_client.describe_services(cluster=cluster, services=[name])
        services = resp.get("services", [])
        if not services:
            raise click.ClickException(f"Service {name} not found")
        task_def_arn = services[0]["taskDefinition"]
    else:
        task_def_arn = name

    td_resp = ecs_client.describe_task_definition(taskDefinition=task_def_arn)
    task_def = td_resp.get("taskDefinition", {})
    containers = task_def.get("containerDefinitions", [])
    if not containers:
        raise click.ClickException("No containers in task definition")

    return task_def_arn, containers


def find_task_id(ecs_client, cluster, service_name=None, task_id=None):
    """Find a running task ID."""
    if task_id:
        return task_id

    kwargs = {"cluster": cluster, "desiredStatus": "RUNNING"}
    if service_name:
        kwargs["serviceName"] = service_name

    resp = ecs_client.list_tasks(**kwargs)
    arns = resp.get("taskArns", [])
    if not arns:
        kwargs["desiredStatus"] = "STOPPED"
        resp = ecs_client.list_tasks(**kwargs)
        arns = resp.get("taskArns", [])
    if not arns:
        raise click.ClickException("No tasks found")
    return arns[0].split("/")[-1]


@click.command()
@click.argument("target")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("--follow", "-f", is_flag=True, help="Stream logs in real-time")
@click.option("--tail", type=int, default=100, help="Number of lines from end")
@click.option("--since", help="Show logs since (e.g., 5m, 1h, 2024-01-01T00:00:00)")
@click.option("--container", "-c", help="Container name")
@click.option("--task-id", help="Specific task ID")
@click.option("--timestamps", is_flag=True, help="Show timestamps")
@click.pass_context
def logs(ctx, target, cluster, follow, tail, since, container, task_id, timestamps):
    """View logs for a service or task.

    TARGET can be: service/<name>, <service-name>, or a task definition family.
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    session = config.get_session()
    ecs = session.client("ecs")
    logs_client = session.client("logs")

    if "/" in target:
        resource_type, name = target.split("/", 1)
    else:
        resource_type, name = "service", target

    task_def_arn, containers = resolve_log_config(ecs, cluster, target)

    if container:
        matched = [c for c in containers if c["name"] == container]
        if not matched:
            available = ", ".join(c["name"] for c in containers)
            raise click.ClickException(f"Container '{container}' not found. Available: {available}")
        selected_container = matched[0]
    else:
        selected_container = containers[0]
        if len(containers) > 1:
            click.echo(f"Using container: {selected_container['name']}", err=True)

    log_config = selected_container.get("logConfiguration", {})
    if log_config.get("logDriver") != "awslogs":
        raise click.ClickException(
            f"Container '{selected_container['name']}' does not use awslogs driver. "
            f"Driver: {log_config.get('logDriver', 'none')}"
        )

    log_group = log_config["options"]["awslogs-group"]
    stream_prefix = log_config["options"].get("awslogs-stream-prefix", "")

    service_name = name if resource_type == "service" else None
    tid = find_task_id(ecs, cluster, service_name=service_name, task_id=task_id)

    log_stream = f"{stream_prefix}/{selected_container['name']}/{tid}"

    start_time = parse_since(since)

    if follow:
        click.echo(f"Streaming logs: {log_group}/{log_stream}", err=True)
        try:
            for event in stream_log_events(logs_client, log_group, log_stream, start_time=start_time):
                _print_event(event, timestamps)
        except KeyboardInterrupt:
            click.echo("\nStopped.", err=True)
    else:
        kwargs = {
            "logGroupName": log_group,
            "logStreamName": log_stream,
            "limit": tail,
            "startFromHead": False,
        }
        if start_time:
            kwargs["startTime"] = start_time

        try:
            resp = logs_client.get_log_events(**kwargs)
            events = resp.get("events", [])
            if not events:
                click.echo("No log events found.")
                return
            for event in events:
                _print_event(event, timestamps)
        except logs_client.exceptions.ResourceNotFoundException:
            click.echo(f"Log stream not found: {log_group}/{log_stream}")
            click.echo("Task may not have started logging yet.")


def _print_event(event, show_timestamps):
    msg = event.get("message", "").rstrip("\n")
    if show_timestamps:
        ts = event.get("timestamp", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        click.echo(f"{dt.isoformat()} {msg}")
    else:
        click.echo(msg)
