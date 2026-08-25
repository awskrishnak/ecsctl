import copy
import click


@click.command()
@click.argument("service_name")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("--image", help="New container image (e.g., myapp:v2)")
@click.option("--task-definition", "task_def_override", help="Task definition to deploy (e.g., my-app:3)")
@click.option("--container", "-c", help="Container name to update (default: first)")
@click.option("--wait/--no-wait", default=False, help="Wait for deployment to stabilize")
@click.option("--dry-run", is_flag=True)
@click.pass_context
def deploy(ctx, service_name, cluster, image, task_def_override, container, wait, dry_run):
    """Deploy a new image or task definition to a service.

    Either --image or --task-definition is required.

    With --image: clones current TD, updates image, registers new revision, updates service.
    With --task-definition: updates service to use the specified TD directly.

    Examples:
        ecsctl deploy my-service --image myrepo/myapp:v2.0
        ecsctl deploy my-service --task-definition my-app:3
    """
    if not image and not task_def_override:
        raise click.ClickException("Either --image or --task-definition is required.")

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

    if task_def_override:
        click.echo(f"Deploying {service_name}: -> {task_def_override}")
        result = executor.call("ecs", "update_service", {
            "cluster": cluster,
            "service": service_name,
            "taskDefinition": task_def_override,
        })
        if not dry_run:
            click.echo(f"Service updated to {task_def_override}.")
        else:
            executor.flush_logs()
            return

    else:
        current_td_arn = services[0]["taskDefinition"]
        td_resp = ecs.describe_task_definition(taskDefinition=current_td_arn)
        task_def = td_resp.get("taskDefinition", {})

        container_defs = copy.deepcopy(task_def.get("containerDefinitions", []))
        if not container_defs:
            raise click.ClickException("No containers in task definition")

        if container:
            matched = [c for c in container_defs if c["name"] == container]
            if not matched:
                available = ", ".join(c["name"] for c in container_defs)
                raise click.ClickException(f"Container '{container}' not found. Available: {available}")
            target_container = matched[0]
        else:
            target_container = container_defs[0]

        old_image = target_container.get("image", "")
        target_container["image"] = image

        click.echo(f"Deploying {service_name}: {old_image} -> {image}")

        register_params = {
            "family": task_def["family"],
            "containerDefinitions": container_defs,
        }
        for key in ["taskRoleArn", "executionRoleArn", "networkMode", "volumes",
                    "placementConstraints", "requiresCompatibilities", "cpu", "memory",
                    "pidMode", "ipcMode", "proxyConfiguration", "runtimePlatform",
                    "ephemeralStorage"]:
            if key in task_def and task_def[key]:
                register_params[key] = task_def[key]

        result = executor.call("ecs", "register_task_definition", register_params)

        if not dry_run:
            new_td_arn = result["taskDefinition"]["taskDefinitionArn"]
            click.echo(f"Registered: {new_td_arn.split('/')[-1]}")

            executor.call("ecs", "update_service", {
                "cluster": cluster,
                "service": service_name,
                "taskDefinition": new_td_arn,
            })
            click.echo(f"Service updated.")
        else:
            executor.flush_logs()
            return

    if not dry_run and wait:
        click.echo("Waiting for service to stabilize...")
        waiter = ecs.get_waiter("services_stable")
        try:
            waiter.wait(
                cluster=cluster,
                services=[service_name],
                WaiterConfig={"Delay": 10, "MaxAttempts": 30},
            )
            click.echo("Deployment complete.")
        except Exception as e:
            raise click.ClickException(f"Deployment did not stabilize: {e}")
