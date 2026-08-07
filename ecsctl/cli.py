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


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)
    ctx.obj["config"] = ConfigManager()


@cli.command()
@cluster_option
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("-f", "--filename", multiple=True, required=True, help="YAML files to apply")
@click.pass_context
def apply(ctx, cluster, dry_run, filename):
    """Apply ECS / AWS resources from YAML files."""
    executor = AWSExecutor(dry_run=dry_run)
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
@click.argument("resource_type")
@click.argument("name", required=False)
@click.pass_context
def get(ctx, cluster, output, resource_type, name):
    """Get ECS / AWS resources."""
    formatter = OutputFormatter(output)
    resource_type = resource_type.lower().replace("-", "").replace("_", "")

    if name:
        try:
            resource = fetch_resource(resource_type, name, cluster)
            if output in ("yaml", "json"):
                formatter.print(resource.to_dict())
            else:
                formatter.print(resource.spec)
        except Exception as e:
            click.echo(f"Error: {e}")
    else:
        _list_resources(resource_type, cluster, formatter)


def _list_resources(resource_type, cluster, formatter):
    import boto3

    if resource_type == "cluster":
        ecs = boto3.client("ecs")
        resp = ecs.list_clusters()
        arns = resp.get("clusterArns", [])
        if not arns:
            click.echo("No clusters found")
            return
        details = ecs.describe_clusters(clusters=arns).get("clusters", [])
        data = [{
            "name": c["clusterName"],
            "status": c["status"],
            "running": c.get("runningTasksCount", 0),
            "pending": c.get("pendingTasksCount", 0),
        } for c in details]
        formatter.print(data)

    elif resource_type == "service":
        if not cluster:
            click.echo("Cluster required. Use --cluster or set AWS_ECS_CLUSTER_NAME")
            return
        ecs = boto3.client("ecs")
        resp = ecs.list_services(cluster=cluster)
        arns = resp.get("serviceArns", [])
        if not arns:
            click.echo("No services found")
            return
        data = []
        for i in range(0, len(arns), 10):
            batch = arns[i:i + 10]
            details = ecs.describe_services(cluster=cluster, services=batch).get("services", [])
            for s in details:
                data.append({
                    "name": s["serviceName"],
                    "taskDefinition": s.get("taskDefinition", "").split("/")[-1],
                    "desired": s.get("desiredCount", 0),
                    "running": s.get("runningCount", 0),
                    "pending": s.get("pendingCount", 0),
                    "status": s.get("status", ""),
                })
        formatter.print(data)

    elif resource_type == "taskdefinition":
        ecs = boto3.client("ecs")
        resp = ecs.list_task_definition_families()
        families = resp.get("families", [])
        data = [{"family": f} for f in families]
        formatter.print(data)

    elif resource_type == "task":
        if not cluster:
            click.echo("Cluster required")
            return
        ecs = boto3.client("ecs")
        resp = ecs.list_tasks(cluster=cluster)
        arns = resp.get("taskArns", [])
        if not arns:
            click.echo("No tasks found")
            return
        details = ecs.describe_tasks(cluster=cluster, tasks=arns).get("tasks", [])
        data = [{
            "taskId": t["taskArn"].split("/")[-1],
            "status": t["lastStatus"],
            "definition": t["taskDefinitionArn"].split("/")[-1],
            "startedAt": str(t.get("startedAt", "N/A")),
        } for t in details]
        formatter.print(data)

    elif resource_type == "loadbalancer":
        elbv2 = boto3.client("elbv2")
        resp = elbv2.describe_load_balancers().get("LoadBalancers", [])
        data = [{
            "name": lb["LoadBalancerName"],
            "type": lb["Type"],
            "scheme": lb["Scheme"],
            "state": lb.get("State", {}).get("Code", "unknown"),
        } for lb in resp]
        formatter.print(data)

    elif resource_type == "autoscalinggroup":
        autoscaling = boto3.client("autoscaling")
        resp = autoscaling.describe_auto_scaling_groups().get("AutoScalingGroups", [])
        data = [{
            "name": g["AutoScalingGroupName"],
            "min": g["MinSize"],
            "max": g["MaxSize"],
            "desired": g["DesiredCapacity"],
            "instances": len(g.get("Instances", [])),
        } for g in resp]
        formatter.print(data)

    elif resource_type == "servicediscoverynamespace":
        sd = boto3.client("servicediscovery")
        resp = sd.list_namespaces().get("Namespaces", [])
        data = [{"name": n["Name"], "type": n["Type"], "id": n["Id"]} for n in resp]
        formatter.print(data)

    elif resource_type == "certificate":
        acm = boto3.client("acm")
        resp = acm.list_certificates().get("CertificateSummaryList", [])
        data = [{"domain": c["DomainName"], "arn": c["CertificateArn"]} for c in resp]
        formatter.print(data)

    elif resource_type == "iamrole":
        iam = boto3.client("iam")
        resp = iam.list_roles().get("Roles", [])
        data = [{
            "name": r["RoleName"],
            "arn": r["Arn"],
            "createDate": str(r["CreateDate"]),
        } for r in resp]
        formatter.print(data)

    else:
        click.echo(f"Listing not yet implemented for {resource_type}")


@cli.command()
@cluster_option
@output_option
@click.argument("resource_type")
@click.argument("name")
@click.pass_context
def describe(ctx, cluster, output, resource_type, name):
    """Describe a specific resource in detail."""
    formatter = OutputFormatter(output)
    try:
        resource = fetch_resource(resource_type, name, cluster)
        if output in ("yaml", "json"):
            formatter.print(resource.to_dict())
        else:
            formatter.print(resource.spec)
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
    """Edit a resource in your default editor with diff preview."""
    target = resource_type.lower().replace("-", "").replace("_", "")
    target_cluster = cluster or ctx.obj["config"].get_cluster()
    edit_resource(target, name, target_cluster, editor, dry_run)


@cli.command()
@cluster_option
@click.option("--dry-run", is_flag=True)
@click.option("-f", "--filename", multiple=True, required=True)
@click.pass_context
def delete(ctx, cluster, dry_run, filename):
    """Delete resources defined in YAML files."""
    executor = AWSExecutor(dry_run=dry_run)
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
            elbv2 = executor.clients["elbv2"]
            lbs = elbv2.describe_load_balancers(Names=[name]).get("LoadBalancers", [])
            if lbs:
                executor.call("elbv2", "delete_load_balancer", {
                    "LoadBalancerArn": lbs[0]["LoadBalancerArn"],
                })
        elif kind == "servicediscoverynamespace":
            sd = executor.clients["servicediscovery"]
            ns = sd.list_namespaces().get("Namespaces", [])
            for n in ns:
                if n["Name"] == name:
                    executor.call("servicediscovery", "delete_namespace", {"Id": n["Id"]})
        elif kind == "servicediscoveryservice":
            sd = executor.clients["servicediscovery"]
            svcs = sd.list_services().get("Services", [])
            for s in svcs:
                if s["Name"] == name:
                    executor.call("servicediscovery", "delete_service", {"Id": s["Id"]})
        elif kind == "certificate":
            acm = executor.clients["acm"]
            certs = acm.list_certificates().get("CertificateSummaryList", [])
            for c in certs:
                if c["DomainName"] == name:
                    executor.call("acm", "delete_certificate", {"CertificateArn": c["CertificateArn"]})
        elif kind == "iamrole":
            executor.call("iam", "delete_role", {"RoleName": name})
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
    """Scale a service desired count."""
    target = cluster or ctx.obj["config"].get_cluster()
    executor = AWSExecutor(dry_run=dry_run)
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
    """Run a one-off task (simplified)."""
    target = cluster or ctx.obj["config"].get_cluster()
    executor = AWSExecutor(dry_run=dry_run)
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


if __name__ == "__main__":
    cli()
