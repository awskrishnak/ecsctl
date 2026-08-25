import click


@click.command(name="wait")
@click.argument("resource_type")
@click.argument("name")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("--for", "condition", required=True,
              type=click.Choice(["stable", "inactive", "running", "stopped"]),
              help="Condition to wait for")
@click.option("--timeout", type=int, default=300, help="Timeout in seconds")
@click.pass_context
def wait_cmd(ctx, resource_type, name, cluster, condition, timeout):
    """Wait for a resource to reach a condition.

    Examples:
        ecsctl wait service my-app --for stable
        ecsctl wait task abc123 --for stopped --timeout 120
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    session = config.get_session()
    ecs = session.client("ecs")

    resource_type = resource_type.lower()
    if resource_type.endswith("s") and resource_type not in ("status",):
        resource_type = resource_type[:-1]

    max_attempts = max(1, timeout // 10)
    waiter_config = {"Delay": 10, "MaxAttempts": max_attempts}

    try:
        if resource_type == "service":
            if condition == "stable":
                waiter = ecs.get_waiter("services_stable")
                click.echo(f"Waiting for service {name} to stabilize (timeout: {timeout}s)...")
                waiter.wait(cluster=cluster, services=[name], WaiterConfig=waiter_config)
            elif condition == "inactive":
                waiter = ecs.get_waiter("services_inactive")
                click.echo(f"Waiting for service {name} to become inactive (timeout: {timeout}s)...")
                waiter.wait(cluster=cluster, services=[name], WaiterConfig=waiter_config)
            else:
                raise click.ClickException(f"Condition '{condition}' not valid for service. Use: stable, inactive")

        elif resource_type == "task":
            if condition == "running":
                waiter = ecs.get_waiter("tasks_running")
                click.echo(f"Waiting for task {name} to start running (timeout: {timeout}s)...")
                waiter.wait(cluster=cluster, tasks=[name], WaiterConfig=waiter_config)
            elif condition == "stopped":
                waiter = ecs.get_waiter("tasks_stopped")
                click.echo(f"Waiting for task {name} to stop (timeout: {timeout}s)...")
                waiter.wait(cluster=cluster, tasks=[name], WaiterConfig=waiter_config)
            else:
                raise click.ClickException(f"Condition '{condition}' not valid for task. Use: running, stopped")
        else:
            raise click.ClickException(f"Wait not supported for {resource_type}. Use: service, task")

        click.echo("Condition met.")
    except Exception as e:
        if "Max attempts exceeded" in str(e) or "Waiter" in str(e):
            raise click.ClickException(f"Timeout: condition '{condition}' not met within {timeout}s")
        raise click.ClickException(str(e))
