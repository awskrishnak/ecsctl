import click


def list_clusters(cluster, formatter, session):
    ecs = session.client("ecs")
    resp = ecs.list_clusters()
    arns = resp.get("clusterArns", [])
    if not arns:
        click.echo("No clusters found")
        return
    details = ecs.describe_clusters(clusters=arns, include=["STATISTICS"]).get("clusters", [])
    data = [{
        "name": c["clusterName"],
        "status": c["status"],
        "services": c.get("activeServicesCount", 0),
        "running": c.get("runningTasksCount", 0),
        "pending": c.get("pendingTasksCount", 0),
        "containerInstances": c.get("registeredContainerInstancesCount", 0),
        "capacityProviders": ", ".join(c.get("capacityProviders", [])) or "-",
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
            td = s.get("taskDefinition", "")
            td_short = td.split("/")[-1] if "/" in td else td
            launch = s.get("launchType", "")
            if not launch:
                cps = s.get("capacityProviderStrategy", [])
                if cps:
                    launch = cps[0].get("capacityProvider", "")
            data.append({
                "name": s["serviceName"],
                "taskDefinition": td_short,
                "desired": s.get("desiredCount", 0),
                "running": s.get("runningCount", 0),
                "pending": s.get("pendingCount", 0),
                "launchType": launch or "N/A",
                "status": s.get("status", ""),
            })
    formatter.print(data)


def list_task_definitions(cluster, formatter, session):
    ecs = session.client("ecs")
    resp = ecs.list_task_definition_families()
    families = resp.get("families", [])
    if not families:
        click.echo("No task definitions found")
        return
    data = []
    for family in families:
        td_arns = ecs.list_task_definitions(familyPrefix=family, sort="DESC", maxResults=1).get("taskDefinitionArns", [])
        if not td_arns:
            data.append({"name": family, "revision": "N/A", "cpu": "N/A", "memory": "N/A", "networkMode": "N/A", "containers": "N/A", "status": "N/A"})
            continue
        td = ecs.describe_task_definition(taskDefinition=td_arns[0]).get("taskDefinition", {})
        containers = td.get("containerDefinitions", [])
        container_names = ", ".join(c["name"] for c in containers)
        data.append({
            "name": family,
            "revision": td.get("revision", "N/A"),
            "cpu": td.get("cpu", "N/A"),
            "memory": td.get("memory", "N/A"),
            "networkMode": td.get("networkMode", "N/A"),
            "containers": container_names,
            "status": td.get("status", "N/A"),
        })
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
    data = []
    for t in details:
        containers = t.get("containers", [])
        container_status = ", ".join(f"{c['name']}({c.get('lastStatus','?')})" for c in containers)
        data.append({
            "taskId": t["taskArn"].split("/")[-1][:12],
            "status": t["lastStatus"],
            "definition": t["taskDefinitionArn"].split("/")[-1],
            "cpu": t.get("cpu", "N/A"),
            "memory": t.get("memory", "N/A"),
            "containers": container_status,
            "startedAt": str(t.get("startedAt", "N/A"))[:19],
        })
    formatter.print(data)


def list_load_balancers(cluster, formatter, session):
    elbv2 = session.client("elbv2")
    resp = elbv2.describe_load_balancers().get("LoadBalancers", [])
    if not resp:
        click.echo("No load balancers found")
        return
    data = [{
        "name": lb["LoadBalancerName"],
        "type": lb["Type"],
        "scheme": lb["Scheme"],
        "dnsName": lb.get("DNSName", "N/A")[:50],
        "state": lb.get("State", {}).get("Code", "unknown"),
        "vpcId": lb.get("VpcId", "N/A"),
    } for lb in resp]
    formatter.print(data)


def list_target_groups(cluster, formatter, session):
    elbv2 = session.client("elbv2")
    resp = elbv2.describe_target_groups().get("TargetGroups", [])
    if not resp:
        click.echo("No target groups found")
        return
    data = [{
        "name": tg["TargetGroupName"],
        "protocol": tg.get("Protocol", "N/A"),
        "port": tg.get("Port", "N/A"),
        "targetType": tg.get("TargetType", ""),
        "healthCheck": tg.get("HealthCheckPath", tg.get("HealthCheckProtocol", "N/A")),
        "vpcId": tg.get("VpcId", "")[-12:],
    } for tg in resp]
    formatter.print(data)


def list_auto_scaling_groups(cluster, formatter, session):
    autoscaling = session.client("autoscaling")
    resp = autoscaling.describe_auto_scaling_groups().get("AutoScalingGroups", [])
    if not resp:
        click.echo("No auto scaling groups found")
        return
    data = []
    for g in resp:
        lt = g.get("LaunchTemplate", {}).get("LaunchTemplateName", "")
        if not lt:
            lt = g.get("LaunchConfigurationName", "N/A")
        data.append({
            "name": g["AutoScalingGroupName"],
            "min": g["MinSize"],
            "max": g["MaxSize"],
            "desired": g["DesiredCapacity"],
            "instances": len(g.get("Instances", [])),
            "launchTemplate": lt[:30],
            "az": ", ".join(az[-2:] for az in g.get("AvailabilityZones", [])),
        })
    formatter.print(data)


def list_sd_namespaces(cluster, formatter, session):
    sd = session.client("servicediscovery")
    resp = sd.list_namespaces().get("Namespaces", [])
    if not resp:
        click.echo("No service discovery namespaces found")
        return
    data = [{
        "name": n["Name"],
        "type": n["Type"],
        "id": n["Id"],
        "description": n.get("Description", "")[:30],
    } for n in resp]
    formatter.print(data)


def list_certificates(cluster, formatter, session):
    acm = session.client("acm")
    resp = acm.list_certificates().get("CertificateSummaryList", [])
    if not resp:
        click.echo("No certificates found")
        return
    data = [{
        "domain": c["DomainName"],
        "status": c.get("Status", "N/A"),
        "type": c.get("Type", "N/A"),
        "inUse": "Yes" if c.get("InUse") else "No",
        "notAfter": str(c.get("NotAfter", "N/A"))[:10],
    } for c in resp]
    formatter.print(data)


def list_iam_roles(cluster, formatter, session):
    iam = session.client("iam")
    resp = iam.list_roles().get("Roles", [])
    if not resp:
        click.echo("No IAM roles found")
        return
    data = [{
        "name": r["RoleName"],
        "path": r.get("Path", "/"),
        "createDate": str(r["CreateDate"])[:10],
        "description": r.get("Description", "")[:40],
    } for r in resp]
    formatter.print(data)


def list_ecr_repositories(cluster, formatter, session):
    ecr = session.client("ecr")
    resp = ecr.describe_repositories().get("repositories", [])
    if not resp:
        click.echo("No ECR repositories found")
        return
    data = [{
        "name": r["repositoryName"],
        "uri": r["repositoryUri"].split("/")[-1],
        "tagMutability": r.get("imageTagMutability", ""),
        "scanOnPush": r.get("imageScanningConfiguration", {}).get("scanOnPush", False),
        "encryption": r.get("encryptionConfiguration", {}).get("encryptionType", "AES256"),
    } for r in resp]
    formatter.print(data)


def list_secrets(cluster, formatter, session):
    sm = session.client("secretsmanager")
    resp = sm.list_secrets().get("SecretList", [])
    if not resp:
        click.echo("No secrets found")
        return
    data = [{
        "name": s["Name"],
        "description": s.get("Description", "")[:30],
        "rotationEnabled": s.get("RotationEnabled", False),
        "lastChanged": str(s.get("LastChangedDate", "N/A"))[:10],
    } for s in resp]
    formatter.print(data)


def list_ssm_parameters(cluster, formatter, session):
    ssm = session.client("ssm")
    resp = ssm.describe_parameters().get("Parameters", [])
    if not resp:
        click.echo("No SSM parameters found")
        return
    data = [{
        "name": p["Name"],
        "type": p.get("Type", ""),
        "tier": p.get("Tier", "Standard"),
        "version": p.get("Version", ""),
        "lastModified": str(p.get("LastModifiedDate", "N/A"))[:10],
    } for p in resp]
    formatter.print(data)


def list_capacity_providers(cluster, formatter, session):
    ecs = session.client("ecs")
    resp = ecs.describe_capacity_providers().get("capacityProviders", [])
    if not resp:
        click.echo("No capacity providers found")
        return
    data = []
    for cp in resp:
        asg_provider = cp.get("autoScalingGroupProvider", {})
        asg_arn = asg_provider.get("autoScalingGroupArn", "")
        asg_name = asg_arn.split("/")[-1] if asg_arn else "N/A (Fargate)"
        scaling = asg_provider.get("managedScaling", {})
        data.append({
            "name": cp["name"],
            "status": cp.get("status", ""),
            "asg": asg_name[:30],
            "managedScaling": scaling.get("status", "N/A"),
            "targetCapacity": scaling.get("targetCapacity", "N/A"),
        })
    formatter.print(data)


def list_nodes(cluster, formatter, session):
    if not cluster:
        click.echo("Cluster required. Use --cluster or set context.")
        return
    ecs = session.client("ecs")
    resp = ecs.list_container_instances(cluster=cluster)
    arns = resp.get("containerInstanceArns", [])
    if not arns:
        click.echo("No container instances (nodes) found")
        return
    details = ecs.describe_container_instances(cluster=cluster, containerInstances=arns).get("containerInstances", [])
    data = []
    for ci in details:
        ec2_id = ci.get("ec2InstanceId", "N/A")
        status = ci.get("status", "N/A")
        agent_connected = ci.get("agentConnected", False)
        running = ci.get("runningTasksCount", 0)
        pending = ci.get("pendingTasksCount", 0)
        registered = ci.get("registeredResources", [])
        remaining = ci.get("remainingResources", [])

        cpu_total = cpu_avail = mem_total = mem_avail = 0
        for r in registered:
            if r["name"] == "CPU":
                cpu_total = r.get("integerValue", 0)
            elif r["name"] == "MEMORY":
                mem_total = r.get("integerValue", 0)
        for r in remaining:
            if r["name"] == "CPU":
                cpu_avail = r.get("integerValue", 0)
            elif r["name"] == "MEMORY":
                mem_avail = r.get("integerValue", 0)

        cap_provider = ci.get("capacityProviderName", "N/A")
        data.append({
            "ec2Instance": ec2_id,
            "status": status,
            "agent": "Connected" if agent_connected else "Disconnected",
            "running": running,
            "pending": pending,
            "cpu": f"{cpu_avail}/{cpu_total}",
            "memory": f"{mem_avail}/{mem_total}MB",
            "capacityProvider": cap_provider,
        })
    formatter.print(data)


LISTERS = {
    "cluster": list_clusters,
    "service": list_services,
    "taskdefinition": list_task_definitions,
    "task": list_tasks,
    "node": list_nodes,
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
