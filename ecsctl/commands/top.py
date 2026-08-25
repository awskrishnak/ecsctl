import click
from datetime import datetime, timedelta, timezone
from ecsctl.output import OutputFormatter


@click.command()
@click.argument("resource_type")
@click.argument("name", required=False)
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("-o", "--output", default="table", type=click.Choice(["table", "json", "yaml"]))
@click.pass_context
def top(ctx, resource_type, name, cluster, output):
    """Show CPU/memory utilization for services or tasks.

    Examples:
        ecsctl top service
        ecsctl top service my-app
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    session = config.get_session()
    ecs = session.client("ecs")
    cw = session.client("cloudwatch")
    formatter = OutputFormatter(output)

    from ecsctl.types import normalize_resource_type
    resource_type = normalize_resource_type(resource_type)

    if resource_type == "service":
        _top_services(ecs, cw, cluster, name, formatter)
    elif resource_type == "task":
        _top_tasks(ecs, cluster, name, formatter)
    else:
        raise click.ClickException(f"top not supported for {resource_type}. Supported: service, task")


def _get_metric(cw, cluster, service_name, metric_name):
    now = datetime.now(timezone.utc)
    resp = cw.get_metric_statistics(
        Namespace="AWS/ECS",
        MetricName=metric_name,
        Dimensions=[
            {"Name": "ClusterName", "Value": cluster},
            {"Name": "ServiceName", "Value": service_name},
        ],
        StartTime=now - timedelta(minutes=5),
        EndTime=now,
        Period=300,
        Statistics=["Average"],
    )
    datapoints = resp.get("Datapoints", [])
    if datapoints:
        latest = sorted(datapoints, key=lambda d: d["Timestamp"])[-1]
        return round(latest["Average"], 1)
    return None


def _top_services(ecs, cw, cluster, name, formatter):
    if name:
        service_names = [name]
    else:
        resp = ecs.list_services(cluster=cluster)
        arns = resp.get("serviceArns", [])
        if not arns:
            click.echo("No services found")
            return
        service_names = [arn.split("/")[-1] for arn in arns]

    data = []
    for svc in service_names:
        cpu = _get_metric(cw, cluster, svc, "CPUUtilization")
        mem = _get_metric(cw, cluster, svc, "MemoryUtilization")

        resp = ecs.describe_services(cluster=cluster, services=[svc])
        services = resp.get("services", [])
        running = services[0].get("runningCount", 0) if services else 0
        desired = services[0].get("desiredCount", 0) if services else 0

        data.append({
            "name": svc,
            "cpu%": f"{cpu}" if cpu is not None else "N/A",
            "memory%": f"{mem}" if mem is not None else "N/A",
            "tasks": f"{running}/{desired}",
        })

    formatter.print(data)


def _top_tasks(ecs, cluster, name, formatter):
    kwargs = {"cluster": cluster, "desiredStatus": "RUNNING"}
    if name:
        kwargs["serviceName"] = name

    resp = ecs.list_tasks(**kwargs)
    arns = resp.get("taskArns", [])
    if not arns:
        click.echo("No running tasks found")
        return

    details = ecs.describe_tasks(cluster=cluster, tasks=arns).get("tasks", [])
    data = []
    for task in details:
        tid = task["taskArn"].split("/")[-1]
        containers = task.get("containers", [])
        cpu_total = 0
        mem_total = 0
        for c in containers:
            cpu_total += int(c.get("cpu", "0") or "0")
            mem_total += int(c.get("memory", "0") or "0")

        data.append({
            "taskId": tid[:12],
            "status": task["lastStatus"],
            "cpu(units)": task.get("cpu", "N/A"),
            "memory(MB)": task.get("memory", "N/A"),
            "definition": task["taskDefinitionArn"].split("/")[-1],
        })

    formatter.print(data)
