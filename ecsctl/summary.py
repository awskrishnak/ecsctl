"""Concise summary views for single-resource get in table mode."""


def summarize_taskdefinition(spec, name, cluster, session):
    family = spec.get("family", name)
    revision = _get_latest_revision(family, session)
    cpu = spec.get("cpu", "N/A")
    memory = spec.get("memory", "N/A")
    network = spec.get("networkMode", "N/A")
    compat = ", ".join(spec.get("requiresCompatibilities", []))
    containers = spec.get("containerDefinitions", [])
    container_names = [c["name"] for c in containers]
    images = [c.get("image", "").split("/")[-1][:50] for c in containers]
    services = _find_services_for_td(family, cluster, session)

    data = [
        {"field": "Family", "value": family},
        {"field": "Revision", "value": revision},
        {"field": "vCPU", "value": f"{cpu} units"},
        {"field": "Memory", "value": f"{memory} MB"},
        {"field": "Network Mode", "value": network},
        {"field": "Launch Type", "value": compat},
        {"field": "Containers", "value": ", ".join(container_names)},
    ]
    for i, c in enumerate(containers):
        data.append({"field": f"  Image [{c['name']}]", "value": images[i]})
    if services:
        data.append({"field": "Services Using", "value": ", ".join(services)})
    else:
        data.append({"field": "Services Using", "value": "(none found)"})
    tags = spec.get("tags", [])
    if tags:
        tag_str = ", ".join(f"{t['key']}={t['value']}" for t in tags[:4])
        data.append({"field": "Tags", "value": tag_str})
    return data


def summarize_service(spec, name, cluster, session):
    td = spec.get("taskDefinition", "N/A")
    if "/" in str(td):
        td = td.split("/")[-1]
    desired = spec.get("desiredCount", 0)
    launch = spec.get("launchType", "")
    if not launch:
        cps = spec.get("capacityProviderStrategy", [])
        if cps:
            launch = ", ".join(f"{cp['capacityProvider']}({cp.get('weight',1)})" for cp in cps)
    network = spec.get("networkMode", spec.get("networkConfiguration", {}).get("awsvpcConfiguration", {}).get("subnets", "N/A"))
    lbs = spec.get("loadBalancers", [])
    lb_info = []
    for lb in lbs:
        tg = lb.get("targetGroupArn", "").split("/")[-2] if lb.get("targetGroupArn") else ""
        port = lb.get("containerPort", "")
        lb_info.append(f"{tg}:{port}")

    data = [
        {"field": "Service", "value": spec.get("serviceName", name)},
        {"field": "Task Definition", "value": td},
        {"field": "Desired Count", "value": desired},
        {"field": "Launch Type", "value": launch or "N/A"},
        {"field": "Load Balancers", "value": ", ".join(lb_info) if lb_info else "(none)"},
    ]

    deploy_config = spec.get("deploymentConfiguration", {})
    if deploy_config:
        data.append({"field": "Min Healthy %", "value": deploy_config.get("minimumHealthyPercent", "N/A")})
        data.append({"field": "Max %", "value": deploy_config.get("maximumPercent", "N/A")})

    tags = spec.get("tags", [])
    if tags:
        tag_str = ", ".join(f"{t.get('key',t.get('Key'))}={t.get('value',t.get('Value'))}" for t in tags[:4])
        data.append({"field": "Tags", "value": tag_str})
    return data


def summarize_cluster(spec, name, cluster, session):
    data = [
        {"field": "Cluster", "value": spec.get("clusterName", name)},
        {"field": "Status", "value": spec.get("status", "N/A")},
    ]
    cps = spec.get("capacityProviders", [])
    if cps:
        data.append({"field": "Capacity Providers", "value": ", ".join(cps)})
    tags = spec.get("tags", [])
    if tags:
        tag_str = ", ".join(f"{t.get('key',t.get('Key'))}={t.get('value',t.get('Value'))}" for t in tags[:4])
        data.append({"field": "Tags", "value": tag_str})
    return data


def summarize_default(spec, name, cluster, session):
    """Fallback: pick readable scalar fields from spec."""
    data = []
    for k, v in spec.items():
        if isinstance(v, (str, int, float, bool)):
            data.append({"field": k, "value": v})
        elif isinstance(v, list) and len(v) == 0:
            continue
        elif isinstance(v, list) and all(isinstance(i, str) for i in v):
            data.append({"field": k, "value": ", ".join(v)})
    return data if data else None


SUMMARIZERS = {
    "taskdefinition": summarize_taskdefinition,
    "service": summarize_service,
    "cluster": summarize_cluster,
}


def get_summary(resource_type, spec, name, cluster, session):
    """Return summary data (list of dicts) or None to fall back to raw spec."""
    summarizer = SUMMARIZERS.get(resource_type, summarize_default)
    try:
        return summarizer(spec, name, cluster, session)
    except Exception:
        return None


def _get_latest_revision(family, session):
    try:
        ecs = session.client("ecs")
        resp = ecs.list_task_definitions(familyPrefix=family, sort="DESC", maxResults=1)
        arns = resp.get("taskDefinitionArns", [])
        if arns:
            return arns[0].split(":")[-1]
    except Exception:
        pass
    return "N/A"


def _find_services_for_td(family, cluster, session):
    if not cluster:
        return []
    try:
        ecs = session.client("ecs")
        resp = ecs.list_services(cluster=cluster)
        arns = resp.get("serviceArns", [])
        if not arns:
            return []
        details = ecs.describe_services(cluster=cluster, services=arns).get("services", [])
        matches = []
        for svc in details:
            td_arn = svc.get("taskDefinition", "")
            if family in td_arn:
                matches.append(svc["serviceName"])
        return matches
    except Exception:
        return []
