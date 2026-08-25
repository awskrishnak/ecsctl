import click


def list_clusters(cluster, formatter, session):
    ecs = session.client("ecs")
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


def list_services(cluster, formatter, session):
    if not cluster:
        click.echo("Cluster required. Use --cluster, set context, or set AWS_ECS_CLUSTER_NAME")
        return
    ecs = session.client("ecs")
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


def list_task_definitions(cluster, formatter, session):
    ecs = session.client("ecs")
    resp = ecs.list_task_definition_families()
    families = resp.get("families", [])
    data = [{"family": f} for f in families]
    formatter.print(data)


def list_tasks(cluster, formatter, session):
    if not cluster:
        click.echo("Cluster required")
        return
    ecs = session.client("ecs")
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


def list_load_balancers(cluster, formatter, session):
    elbv2 = session.client("elbv2")
    resp = elbv2.describe_load_balancers().get("LoadBalancers", [])
    data = [{
        "name": lb["LoadBalancerName"],
        "type": lb["Type"],
        "scheme": lb["Scheme"],
        "state": lb.get("State", {}).get("Code", "unknown"),
    } for lb in resp]
    formatter.print(data)


def list_target_groups(cluster, formatter, session):
    elbv2 = session.client("elbv2")
    resp = elbv2.describe_target_groups().get("TargetGroups", [])
    data = [{
        "name": tg["TargetGroupName"],
        "protocol": tg.get("Protocol", "N/A"),
        "port": tg.get("Port", "N/A"),
        "targetType": tg.get("TargetType", ""),
        "vpcId": tg.get("VpcId", ""),
    } for tg in resp]
    formatter.print(data)


def list_auto_scaling_groups(cluster, formatter, session):
    autoscaling = session.client("autoscaling")
    resp = autoscaling.describe_auto_scaling_groups().get("AutoScalingGroups", [])
    data = [{
        "name": g["AutoScalingGroupName"],
        "min": g["MinSize"],
        "max": g["MaxSize"],
        "desired": g["DesiredCapacity"],
        "instances": len(g.get("Instances", [])),
    } for g in resp]
    formatter.print(data)


def list_sd_namespaces(cluster, formatter, session):
    sd = session.client("servicediscovery")
    resp = sd.list_namespaces().get("Namespaces", [])
    data = [{"name": n["Name"], "type": n["Type"], "id": n["Id"]} for n in resp]
    formatter.print(data)


def list_certificates(cluster, formatter, session):
    acm = session.client("acm")
    resp = acm.list_certificates().get("CertificateSummaryList", [])
    data = [{"domain": c["DomainName"], "arn": c["CertificateArn"]} for c in resp]
    formatter.print(data)


def list_iam_roles(cluster, formatter, session):
    iam = session.client("iam")
    resp = iam.list_roles().get("Roles", [])
    data = [{
        "name": r["RoleName"],
        "arn": r["Arn"],
        "createDate": str(r["CreateDate"]),
    } for r in resp]
    formatter.print(data)


def list_ecr_repositories(cluster, formatter, session):
    ecr = session.client("ecr")
    resp = ecr.describe_repositories().get("repositories", [])
    data = [{
        "name": r["repositoryName"],
        "uri": r["repositoryUri"],
        "tagMutability": r.get("imageTagMutability", ""),
        "scanOnPush": r.get("imageScanningConfiguration", {}).get("scanOnPush", False),
    } for r in resp]
    formatter.print(data)


def list_secrets(cluster, formatter, session):
    sm = session.client("secretsmanager")
    resp = sm.list_secrets().get("SecretList", [])
    data = [{
        "name": s["Name"],
        "description": s.get("Description", ""),
        "lastChanged": str(s.get("LastChangedDate", "N/A")),
    } for s in resp]
    formatter.print(data)


def list_ssm_parameters(cluster, formatter, session):
    ssm = session.client("ssm")
    resp = ssm.describe_parameters().get("Parameters", [])
    data = [{
        "name": p["Name"],
        "type": p.get("Type", ""),
        "version": p.get("Version", ""),
        "lastModified": str(p.get("LastModifiedDate", "N/A")),
    } for p in resp]
    formatter.print(data)


def list_capacity_providers(cluster, formatter, session):
    ecs = session.client("ecs")
    resp = ecs.describe_capacity_providers().get("capacityProviders", [])
    data = [{
        "name": cp["name"],
        "status": cp.get("status", ""),
        "managedScaling": cp.get("autoScalingGroupProvider", {}).get("managedScaling", {}).get("status", "N/A"),
    } for cp in resp]
    formatter.print(data)


LISTERS = {
    "cluster": list_clusters,
    "service": list_services,
    "taskdefinition": list_task_definitions,
    "task": list_tasks,
    "loadbalancer": list_load_balancers,
    "targetgroup": list_target_groups,
    "autoscalinggroup": list_auto_scaling_groups,
    "servicediscoverynamespace": list_sd_namespaces,
    "certificate": list_certificates,
    "iamrole": list_iam_roles,
    "ecrrepository": list_ecr_repositories,
    "secret": list_secrets,
    "ssmparameter": list_ssm_parameters,
    "capacityprovider": list_capacity_providers,
}


def list_resources(resource_type, cluster, formatter, session):
    lister = LISTERS.get(resource_type)
    if not lister:
        click.echo(f"Unknown resource type: {resource_type}")
        click.echo(f"Available: {', '.join(sorted(LISTERS.keys()))}")
        return
    lister(cluster, formatter, session)
