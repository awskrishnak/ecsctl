import os
import click
from ecsctl import __version__
from ecsctl.config import ConfigManager
from ecsctl.executor import AWSExecutor
from ecsctl.resources.base import ECSResource
from ecsctl.fetcher import fetch_resource
from ecsctl.applier import apply_resource
from ecsctl.editor import edit_resource
from ecsctl.output import OutputFormatter


from ecsctl.types import normalize_resource_type


def output_option(f):
    return click.option(
        "-o", "--output",
        default="table",
        type=click.Choice(["table", "json", "yaml"]),
        help="Output format",
    )(f)


def cluster_option(f):
    return click.option(
        "--cluster",
        envvar="AWS_ECS_CLUSTER_NAME",
        help="ECS cluster name",
    )(f)


EPILOG = """\b
Resource Types (with short aliases):
  cluster        service (svc)     task             taskdefinition (td)
  node (ci)      loadbalancer (lb/alb)              targetgroup (tg)
  autoscalinggroup (asg)           capacityprovider (cp)
  ecrrepository (ecr/repo)         secret (sec)
  ssmparameter (ssm/param)         certificate (cert)
  servicediscoverynamespace (ns)   iamrole (role)

\b
Examples:
  ecsctl get svc
  ecsctl get td
  ecsctl get node
  ecsctl describe asg my-asg -o yaml
  ecsctl logs my-service --follow
  ecsctl deploy my-service --image repo:v2
  ecsctl rollback my-service
  ecsctl apply -f service.yaml --dry-run
  ecsctl config set prod --cluster-name my-cluster --aws-profile prod
"""


@click.group(epilog=EPILOG)
@click.version_option(version=__version__, prog_name="ecsctl")
@click.pass_context
def cli(ctx):
    """kubectl-style CLI for managing AWS ECS clusters and infrastructure."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = ConfigManager()


@cli.command()
@cluster_option
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("-f", "--filename", multiple=True, required=True, help="YAML files to apply")
@click.pass_context
def apply(ctx, cluster, dry_run, filename):
    """Create or update resources from YAML manifests."""
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    executor = AWSExecutor(dry_run=dry_run, session=config.get_session())
    for f in filename:
        if not os.path.exists(f):
            click.echo(f"File not found: {f}")
            continue
        resource = ECSResource.from_yaml(f)
        target_cluster = resource.metadata.namespace or cluster or ctx.obj["config"].get_cluster()
        if not target_cluster and resource.kind.lower() in ["service", "task"]:
            click.echo(f"Cluster required for {resource.kind}")
            continue
        click.echo(f"Applying {resource.kind}/{resource.metadata.name}...")
        result = apply_resource(resource, executor, target_cluster)
        if not dry_run:
            click.echo(result)
    if dry_run:
        executor.flush_logs()


@cli.command()
@cluster_option
@output_option
@click.option("-w", "--watch", is_flag=True, help="Watch for changes (poll every 2s)")
@click.argument("resource_type")
@click.argument("name", required=False)
@click.pass_context
def get(ctx, cluster, output, watch, resource_type, name):
    """List resources or get a specific resource by name."""
    cluster = cluster or ctx.obj["config"].get_cluster()
    formatter = OutputFormatter(output)
    resource_type = normalize_resource_type(resource_type)

    config = ctx.obj["config"]
    if name:
        try:
            resource = fetch_resource(resource_type, name, cluster, session=config.get_session())
            if output in ("yaml", "json"):
                formatter.print(resource.to_dict())
            else:
                from ecsctl.summary import get_summary
                summary = get_summary(resource_type, resource.spec, name, cluster, config.get_session())
                if summary:
                    formatter.print(summary)
                else:
                    formatter.print(resource.spec)
        except Exception as e:
            click.echo(f"Error: {e}")
    elif watch:
        from ecsctl.watcher import watch_loop
        watch_loop(lambda: _list_resources(resource_type, cluster, formatter, session=config.get_session()))
    else:
        _list_resources(resource_type, cluster, formatter, session=config.get_session())


def _list_resources(resource_type, cluster, formatter, session=None):
    from ecsctl.lister import list_resources
    import boto3
    session = session or boto3.Session()
    list_resources(resource_type, cluster, formatter, session)


@cli.command()
@cluster_option
@output_option
@click.argument("resource_type")
@click.argument("name")
@click.pass_context
def describe(ctx, cluster, output, resource_type, name):
    """Show detailed info for a named resource."""
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    resource_type = normalize_resource_type(resource_type)
    formatter = OutputFormatter(output)
    try:
        resource = fetch_resource(resource_type, name, cluster, session=config.get_session())
        if output in ("yaml", "json"):
            formatter.print(resource.to_dict())
        else:
            from ecsctl.output import print_describe
            click.echo(f"Name:\t\t{resource.metadata.name}")
            click.echo(f"Kind:\t\t{resource.kind}")
            if resource.metadata.namespace:
                click.echo(f"Namespace:\t{resource.metadata.namespace}")
            click.echo("")
            print_describe(resource.spec)
    except Exception as e:
        click.echo(f"Error: {e}")


@cli.command()
@cluster_option
@click.option("--dry-run", is_flag=True)
@click.option("--editor", envvar="EDITOR", default="vim")
@click.argument("resource_type")
@click.argument("name")
@click.pass_context
def edit(ctx, cluster, dry_run, editor, resource_type, name):
    """Edit a live resource in $EDITOR, preview diff, then apply."""
    config = ctx.obj["config"]
    target = normalize_resource_type(resource_type)
    target_cluster = cluster or config.get_cluster()
    edit_resource(target, name, target_cluster, editor, dry_run, session=config.get_session())


@cli.command()
@cluster_option
@click.option("--dry-run", is_flag=True)
@click.option("-f", "--filename", multiple=True, required=True)
@click.pass_context
def delete(ctx, cluster, dry_run, filename):
    """Delete resources defined in YAML manifests."""
    config = ctx.obj["config"]
    cluster = cluster or config.get_cluster()
    executor = AWSExecutor(dry_run=dry_run, session=config.get_session())
    for f in filename:
        resource = ECSResource.from_yaml(f)
        kind = resource.kind.lower().replace("-", "").replace("_", "")
        name = resource.metadata.name
        target_cluster = resource.metadata.namespace or cluster or ctx.obj["config"].get_cluster()

        click.echo(f"Deleting {resource.kind}/{name}...")

        if kind == "service":
            executor.call("ecs", "delete_service", {
                "cluster": target_cluster,
                "service": name,
                "force": True,
            })
        elif kind == "taskdefinition":
            executor.call("ecs", "deregister_task_definition", {"taskDefinition": name})
        elif kind == "cluster":
            executor.call("ecs", "delete_cluster", {"cluster": name})
        elif kind == "autoscalinggroup":
            executor.call("autoscaling", "delete_auto_scaling_group", {
                "AutoScalingGroupName": name,
                "ForceDelete": True,
            })
        elif kind == "loadbalancer":
            elbv2 = executor.client("elbv2")
            lbs = elbv2.describe_load_balancers(Names=[name]).get("LoadBalancers", [])
            if lbs:
                executor.call("elbv2", "delete_load_balancer", {
                    "LoadBalancerArn": lbs[0]["LoadBalancerArn"],
                })
        elif kind == "servicediscoverynamespace":
            sd = executor.client("servicediscovery")
            ns = sd.list_namespaces().get("Namespaces", [])
            for n in ns:
                if n["Name"] == name:
                    executor.call("servicediscovery", "delete_namespace", {"Id": n["Id"]})
        elif kind == "servicediscoveryservice":
            sd = executor.client("servicediscovery")
            svcs = sd.list_services().get("Services", [])
            for s in svcs:
                if s["Name"] == name:
                    executor.call("servicediscovery", "delete_service", {"Id": s["Id"]})
        elif kind == "certificate":
            acm = executor.client("acm")
            certs = acm.list_certificates().get("CertificateSummaryList", [])
            for c in certs:
                if c["DomainName"] == name:
                    executor.call("acm", "delete_certificate", {"CertificateArn": c["CertificateArn"]})
        elif kind == "iamrole":
            executor.call("iam", "delete_role", {"RoleName": name})
        elif kind == "targetgroup":
            elbv2 = executor.client("elbv2")
            tgs = elbv2.describe_target_groups(Names=[name]).get("TargetGroups", [])
            if tgs:
                executor.call("elbv2", "delete_target_group", {
                    "TargetGroupArn": tgs[0]["TargetGroupArn"],
                })
        elif kind == "ecrrepository":
            executor.call("ecr", "delete_repository", {
                "repositoryName": name, "force": True,
            })
        elif kind == "secret":
            executor.call("secretsmanager", "delete_secret", {
                "SecretId": name, "ForceDeleteWithoutRecovery": True,
            })
        elif kind == "ssmparameter":
            executor.call("ssm", "delete_parameter", {"Name": name})
        elif kind == "capacityprovider":
            executor.call("ecs", "delete_capacity_provider", {
                "capacityProvider": name,
            })
        else:
            click.echo(f"Delete not implemented for {kind}")

    if dry_run:
        executor.flush_logs()


@cli.group(name="config")
def config_cmd():
    """Manage ecsctl configuration contexts."""
    pass


@config_cmd.command("set")
@click.argument("name")
@click.option("--cluster-name")
@click.option("--aws-profile")
@click.option("--aws-region")
def config_set(name, cluster_name, aws_profile, aws_region):
    """Save a context configuration."""
    mgr = ConfigManager()
    mgr.set_context(name, cluster_name=cluster_name, aws_profile=aws_profile, aws_region=aws_region)
    click.echo(f"Context '{name}' saved.")


@config_cmd.command("show")
@click.option("--show-all", is_flag=True)
def config_show(show_all):
    """Show current configuration."""
    mgr = ConfigManager()
    if show_all:
        for ctx_name, cfg in mgr.contexts.items():
            click.echo(f"{ctx_name}: {cfg}")
    else:
        click.echo(mgr.get_current())


@config_cmd.command("context")
@click.argument("name")
def config_context(name):
    """Switch active context."""
    mgr = ConfigManager()
    mgr.switch_context(name)
    click.echo(f"Switched to context '{name}'")


@cli.command()
@cluster_option
@click.argument("service_name")
@click.argument("count", type=int)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def scale(ctx, cluster, service_name, count, dry_run):
    """Scale a service to a desired task count."""
    config = ctx.obj["config"]
    target = cluster or config.get_cluster()
    executor = AWSExecutor(dry_run=dry_run, session=config.get_session())
    result = executor.call("ecs", "update_service", {
        "cluster": target,
        "service": service_name,
        "desiredCount": count,
    })
    click.echo(result)


@cli.command()
@cluster_option
@click.option("--image", required=True)
@click.option("--name", required=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def run(ctx, cluster, image, name, dry_run):
    """Run a one-off Fargate task from an image."""
    config = ctx.obj["config"]
    target = cluster or config.get_cluster()
    executor = AWSExecutor(dry_run=dry_run, session=config.get_session())
    td = executor.call("ecs", "register_task_definition", {
        "family": name,
        "containerDefinitions": [{
            "name": name,
            "image": image,
            "essential": True,
        }],
    })
    if not dry_run:
        task_def_arn = td["taskDefinition"]["taskDefinitionArn"]
        result = executor.call("ecs", "run_task", {
            "cluster": target,
            "taskDefinition": task_def_arn,
            "launchType": "FARGATE",
        })
        click.echo(result)
    else:
        executor.flush_logs()


from ecsctl.commands.logs import logs
from ecsctl.commands.exec import exec_cmd
from ecsctl.commands.events import events
from ecsctl.commands.top import top
from ecsctl.commands.rollback import rollback
from ecsctl.commands.restart import restart
from ecsctl.commands.deploy import deploy
from ecsctl.commands.wait import wait_cmd
from ecsctl.commands.diff import diff_cmd

cli.add_command(logs)
cli.add_command(exec_cmd, name="exec")
cli.add_command(events)
cli.add_command(top)
cli.add_command(rollback)
cli.add_command(restart)
cli.add_command(deploy)
cli.add_command(wait_cmd, name="wait")
cli.add_command(diff_cmd, name="diff")


if __name__ == "__main__":
    cli()
