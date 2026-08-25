import click


@click.command()
@click.argument("service_name")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def restart(ctx, service_name, cluster, dry_run):
    """Rolling restart a service (keeps current task definition)."""
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    from ecsctl.executor import AWSExecutor
    executor = AWSExecutor(dry_run=dry_run, session=config.get_session())

    click.echo(f"Restarting {service_name}...")

    result = executor.call("ecs", "update_service", {
        "cluster": cluster,
        "service": service_name,
        "forceNewDeployment": True,
    })

    if dry_run:
        executor.flush_logs()
    else:
        click.echo(f"Restart initiated for {service_name}.")
