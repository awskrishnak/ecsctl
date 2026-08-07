import boto3
from typing import Any
from ecsctl.resources.base import ECSResource, Metadata

# Read-only / AWS-managed fields to strip when generating declarative YAML
READONLY_STRIPPERS = {
    "TaskDefinition": [
        "taskDefinitionArn", "revision", "status", "requiresAttributes",
        "compatibilities", "registeredAt", "registeredBy", "deregisteredAt",
    ],
    "Service": [
        "serviceArn", "clusterArn", "createdAt", "createdBy", "deployments",
        "events", "runningCount", "pendingCount", "status",
    ],
    "Cluster": [
        "clusterArn", "registeredContainerInstancesCount", "runningTasksCount",
        "pendingTasksCount", "activeServicesCount", "statistics", "attachments",
        "settings",
    ],
    "LoadBalancer": [
        "LoadBalancerArn", "CanonicalHostedZoneId", "CreatedTime", "State",
        "DNSName", "VpcId",
    ],
    "AutoScalingGroup": [
        "AutoScalingGroupARN", "CreatedTime", "AvailabilityZones",
        "Instances", "HealthCheckType", "TargetGroupARNs", "SuspendedProcesses",
        "EnabledMetrics", "Tags",
    ],
    "ServiceDiscoveryNamespace": [
        "Arn", "Id", "CreateDate", "CreatorRequestId",
    ],
    "ServiceDiscoveryService": [
        "Arn", "Id", "CreateDate", "CreatorRequestId", "NamespaceId",
    ],
    "Certificate": [
        "CertificateArn", "CreatedAt", "Status", "DomainValidationOptions",
        "Subject", "Serial", "NotBefore", "NotAfter", "InUseBy", "KeyAlgorithm",
        "SignatureAlgorithm",
    ],
    "IAMRole": [
        "Arn", "RoleId", "CreateDate", "RoleLastUsed", "MaxSessionDuration",
    ],
}


def strip_readonly(kind: str, data: dict) -> dict:
    strippers = READONLY_STRIPPERS.get(kind, [])
    return {k: v for k, v in data.items() if k not in strippers}


def fetch_task_definition(name: str) -> dict:
    ecs = boto3.client("ecs")
    resp = ecs.describe_task_definition(taskDefinition=name)
    return resp.get("taskDefinition", {})


def fetch_service(cluster: str, name: str) -> dict:
    ecs = boto3.client("ecs")
    resp = ecs.describe_services(cluster=cluster, services=[name])
    services = resp.get("services", [])
    if not services:
        raise ValueError(f"Service {name} not found in cluster {cluster}")
    return services[0]


def fetch_cluster(name: str) -> dict:
    ecs = boto3.client("ecs")
    resp = ecs.describe_clusters(clusters=[name])
    clusters = resp.get("clusters", [])
    if not clusters:
        raise ValueError(f"Cluster {name} not found")
    return clusters[0]


def fetch_alb(name: str) -> dict:
    elbv2 = boto3.client("elbv2")
    resp = elbv2.describe_load_balancers(Names=[name])
    lbs = resp.get("LoadBalancers", [])
    if not lbs:
        raise ValueError(f"LoadBalancer {name} not found")
    lb = lbs[0]
    # Enrich with listeners
    listeners = elbv2.describe_listeners(LoadBalancerArn=lb["LoadBalancerArn"]).get("Listeners", [])
    lb["Listeners"] = listeners
    return lb


def fetch_asg(name: str) -> dict:
    autoscaling = boto3.client("autoscaling")
    resp = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
    groups = resp.get("AutoScalingGroups", [])
    if not groups:
        raise ValueError(f"AutoScalingGroup {name} not found")
    return groups[0]


def fetch_sd_namespace(name: str) -> dict:
    sd = boto3.client("servicediscovery")
    resp = sd.list_namespaces()
    for ns in resp.get("Namespaces", []):
        if ns["Name"] == name:
            return ns
    raise ValueError(f"Namespace {name} not found")


def fetch_sd_service(name: str) -> dict:
    sd = boto3.client("servicediscovery")
    resp = sd.list_services()
    for svc in resp.get("Services", []):
        if svc["Name"] == name:
            return svc
    raise ValueError(f"ServiceDiscoveryService {name} not found")


def fetch_certificate(name: str) -> dict:
    acm = boto3.client("acm")
    if name.startswith("arn:"):
        resp = acm.describe_certificate(CertificateArn=name)
        return resp.get("Certificate", {})
    certs = acm.list_certificates().get("CertificateSummaryList", [])
    for c in certs:
        if c.get("DomainName") == name:
            resp = acm.describe_certificate(CertificateArn=c["CertificateArn"])
            return resp.get("Certificate", {})
    raise ValueError(f"Certificate {name} not found")


def fetch_iam_role(name: str) -> dict:
    iam = boto3.client("iam")
    resp = iam.get_role(RoleName=name)
    role = resp.get("Role", {})
    # Enrich with policy info
    attached = iam.list_attached_role_policies(RoleName=name).get("AttachedPolicies", [])
    role["AttachedPolicies"] = attached
    inline_names = iam.list_role_policies(RoleName=name).get("PolicyNames", [])
    role["InlinePolicies"] = []
    for p in inline_names:
        pol = iam.get_role_policy(RoleName=name, PolicyName=p)
        role["InlinePolicies"].append({
            "PolicyName": p,
            "PolicyDocument": pol.get("PolicyDocument", {}),
        })
    return role


FETCHERS = {
    "taskdefinition": fetch_task_definition,
    "service": fetch_service,
    "cluster": fetch_cluster,
    "loadbalancer": fetch_alb,
    "autoscalinggroup": fetch_asg,
    "servicediscoverynamespace": fetch_sd_namespace,
    "servicediscoveryservice": fetch_sd_service,
    "certificate": fetch_certificate,
    "iamrole": fetch_iam_role,
}


def fetch_resource(kind: str, name: str, cluster: str = None) -> ECSResource:
    kind_norm = kind.lower().replace("-", "").replace("_", "")
    fetcher = FETCHERS.get(kind_norm)
    if not fetcher:
        raise ValueError(f"Unknown resource kind: {kind}")

    if kind_norm == "service":
        raw = fetcher(cluster, name)
    else:
        raw = fetcher(name)

    clean = strip_readonly(kind, raw)
    return ECSResource(
        apiVersion="ecs/v1",
        kind=kind,
        metadata=Metadata(name=name, namespace=cluster),
        spec=clean,
    )
