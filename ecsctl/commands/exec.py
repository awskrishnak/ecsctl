import json
import shutil
import subprocess
import click


@click.command(name="exec")
@click.argument("target")
@click.option("--cluster", envvar="AWS_ECS_CLUSTER_NAME", help="ECS cluster name")
@click.option("--container", "-c", help="Container name")
@click.option("--command", "cmd", default="/bin/sh", help="Command to run")
@click.option("--task-id", help="Specific task ID")
@click.pass_context
def exec_cmd(ctx, target, cluster, container, cmd, task_id):
    """Execute a command in a running container.

    TARGET can be: service/<name> or a task ID.
    """
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    if not cluster:
        raise click.ClickException("Cluster required. Use --cluster or set context.")

    if not shutil.which("session-manager-plugin"):
        raise click.ClickException(
            "session-manager-plugin not found. Install it:\n"
            "  https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"
        )

    session = config.get_session()
    ecs = session.client("ecs")

    if task_id:
        tid = task_id
    elif "/" in target:
        resource_type, name = target.split("/", 1)
        if resource_type == "service":
            resp = ecs.list_tasks(cluster=cluster, serviceName=name, desiredStatus="RUNNING")
            arns = resp.get("taskArns", [])
            if not arns:
                raise click.ClickException(f"No running tasks for service {name}")
            tid = arns[0].split("/")[-1]
        else:
            tid = name
    else:
        resp = ecs.list_tasks(cluster=cluster, serviceName=target, desiredStatus="RUNNING")
        arns = resp.get("taskArns", [])
        if not arns:
            raise click.ClickException(f"No running tasks for service {target}")
        tid = arns[0].split("/")[-1]

    if not container:
        task_resp = ecs.describe_tasks(cluster=cluster, tasks=[tid])
        tasks = task_resp.get("tasks", [])
        if not tasks:
            raise click.ClickException(f"Task {tid} not found")
        containers = tasks[0].get("containers", [])
        if not containers:
            raise click.ClickException("No containers in task")
        container = containers[0]["name"]
        if len(containers) > 1:
            click.echo(f"Using container: {container}", err=True)

    try:
        resp = ecs.execute_command(
            cluster=cluster,
            task=tid,
            container=container,
            command=cmd,
            interactive=True,
        )
    except ecs.exceptions.InvalidParameterException as e:
        if "execute command" in str(e).lower():
            raise click.ClickException(
                f"ECS Exec not enabled on this task/service. Enable with:\n"
                f"  ecsctl apply with enableExecuteCommand: true in service spec"
            )
        raise click.ClickException(str(e))

    session_info = resp.get("session", {})
    session_id = session_info.get("sessionId")
    stream_url = session_info.get("streamUrl")
    token_value = session_info.get("tokenValue")

    region = session.region_name or config.get_current().get("aws_region", "us-east-1")

    ssm_request = json.dumps({
        "SessionId": session_id,
        "StreamUrl": stream_url,
        "TokenValue": token_value,
    })

    endpoint = f"https://ssm.{region}.amazonaws.com"

    subprocess.call([
        "session-manager-plugin",
        ssm_request,
        region,
        "StartSession",
        "",
        json.dumps({"Target": tid}),
        endpoint,
    ])
