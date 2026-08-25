import click


@click.command()
@click.argument("service_name")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("--revision", type=int, help="Specific revision to roll back to (default: previous)")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def rollback(ctx, service_name, cluster, revision, dry_run):
    """Roll back a service to a previous task definition revision.

    Example: ecsctl rollback my-service --revision 3
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    from ecsctl.executor import AWSExecutor
    executor = AWSExecutor(dry_run=dry_run, session=config.get_session())
    ecs = executor.client("ecs")

    resp = ecs.describe_services(cluster=cluster, services=[service_name])
    services = resp.get("services", [])
    if not services:
        raise click.ClickException(f"Service {service_name} not found")

    current_td = services[0]["taskDefinition"]
    family = current_td.split("/")[-1].rsplit(":", 1)[0]
    current_rev = int(current_td.split(":")[-1])

    if revision:
        target_td = f"{family}:{revision}"
    else:
        revisions = ecs.list_task_definitions(
            familyPrefix=family, sort="DESC", maxResults=5
        ).get("taskDefinitionArns", [])

        previous = None
        for arn in revisions:
            rev = int(arn.split(":")[-1])
            if rev < current_rev:
                previous = arn
                break

        if not previous:
            raise click.ClickException(f"No previous revision found for {family}")
        target_td = previous

    click.echo(f"Rolling back {service_name}: {family}:{current_rev} -> {target_td.split('/')[-1]}")

    result = executor.call("ecs", "update_service", {
        "cluster": cluster,
        "service": service_name,
        "taskDefinition": target_td,
    })

    if dry_run:
        executor.flush_logs()
    else:
        click.echo("Rollback initiated. Use 'ecsctl events service {}' to monitor.".format(service_name))
