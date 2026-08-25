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
    "TargetGroup": [
        "TargetGroupArn", "LoadBalancerArns", "HealthCheckPort",
    ],
    "ECRRepository": [
        "repositoryArn", "registryId", "repositoryUri", "createdAt",
    ],
    "Secret": [
        "ARN", "RotationEnabled", "RotationRules", "LastRotatedDate",
        "LastChangedDate", "LastAccessedDate", "DeletedDate", "CreatedDate",
        "VersionIdsToStages", "OwningService", "ReplicationStatus",
    ],
    "SSMParameter": [
        "ARN", "LastModifiedDate", "Version", "DataType",
    ],
    "CapacityProvider": [
        "capacityProviderArn", "status", "updateStatus", "updateStatusReason",
    ],
}


def strip_readonly(kind: str, data: dict) -> dict:
    strippers = READONLY_STRIPPERS.get(kind, [])
    return {k: v for k, v in data.items() if k not in strippers}


def fetch_task_definition(name: str, session=None) -> dict:
    session = session or boto3.Session()
    ecs = session.client("ecs")
    resp = ecs.describe_task_definition(taskDefinition=name)
    return resp.get("taskDefinition", {})


def fetch_service(cluster: str, name: str, session=None) -> dict:
    session = session or boto3.Session()
    ecs = session.client("ecs")
    resp = ecs.describe_services(cluster=cluster, services=[name])
    services = resp.get("services", [])
    if not services:
        raise ValueError(f"Service {name} not found in cluster {cluster}")
    return services[0]


def fetch_cluster(name: str, session=None) -> dict:
    session = session or boto3.Session()
    ecs = session.client("ecs")
    resp = ecs.describe_clusters(clusters=[name])
    clusters = resp.get("clusters", [])
    if not clusters:
        raise ValueError(f"Cluster {name} not found")
    return clusters[0]


def fetch_alb(name: str, session=None) -> dict:
    session = session or boto3.Session()
    elbv2 = session.client("elbv2")
    resp = elbv2.describe_load_balancers(Names=[name])
    lbs = resp.get("LoadBalancers", [])
    if not lbs:
        raise ValueError(f"LoadBalancer {name} not found")
    lb = lbs[0]
    listeners = elbv2.describe_listeners(LoadBalancerArn=lb["LoadBalancerArn"]).get("Listeners", [])
    lb["Listeners"] = listeners
    return lb


def fetch_asg(name: str, session=None) -> dict:
    session = session or boto3.Session()
    autoscaling = session.client("autoscaling")
    resp = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
    groups = resp.get("AutoScalingGroups", [])
    if not groups:
        raise ValueError(f"AutoScalingGroup {name} not found")
    return groups[0]


def fetch_sd_namespace(name: str, session=None) -> dict:
    session = session or boto3.Session()
    sd = session.client("servicediscovery")
    resp = sd.list_namespaces()
    for ns in resp.get("Namespaces", []):
        if ns["Name"] == name:
            return ns
    raise ValueError(f"Namespace {name} not found")


def fetch_sd_service(name: str, session=None) -> dict:
    session = session or boto3.Session()
    sd = session.client("servicediscovery")
    resp = sd.list_services()
    for svc in resp.get("Services", []):
        if svc["Name"] == name:
            return svc
    raise ValueError(f"ServiceDiscoveryService {name} not found")


def fetch_certificate(name: str, session=None) -> dict:
    session = session or boto3.Session()
    acm = session.client("acm")
    if name.startswith("arn:"):
        resp = acm.describe_certificate(CertificateArn=name)
        return resp.get("Certificate", {})
    certs = acm.list_certificates().get("CertificateSummaryList", [])
    for c in certs:
        if c.get("DomainName") == name:
            resp = acm.describe_certificate(CertificateArn=c["CertificateArn"])
            return resp.get("Certificate", {})
    raise ValueError(f"Certificate {name} not found")


def fetch_iam_role(name: str, session=None) -> dict:
    session = session or boto3.Session()
    iam = session.client("iam")
    resp = iam.get_role(RoleName=name)
    role = resp.get("Role", {})
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


def fetch_target_group(name: str, session=None) -> dict:
    session = session or boto3.Session()
    elbv2 = session.client("elbv2")
    resp = elbv2.describe_target_groups(Names=[name])
    tgs = resp.get("TargetGroups", [])
    if not tgs:
        raise ValueError(f"TargetGroup {name} not found")
    return tgs[0]


def fetch_ecr_repository(name: str, session=None) -> dict:
    session = session or boto3.Session()
    ecr = session.client("ecr")
    resp = ecr.describe_repositories(repositoryNames=[name])
    repos = resp.get("repositories", [])
    if not repos:
        raise ValueError(f"ECR Repository {name} not found")
    return repos[0]


def fetch_secret(name: str, session=None) -> dict:
    session = session or boto3.Session()
    sm = session.client("secretsmanager")
    resp = sm.describe_secret(SecretId=name)
    return resp


def fetch_ssm_parameter(name: str, session=None) -> dict:
    session = session or boto3.Session()
    ssm = session.client("ssm")
    resp = ssm.get_parameter(Name=name, WithDecryption=False)
    return resp.get("Parameter", {})


def fetch_capacity_provider(name: str, session=None) -> dict:
    session = session or boto3.Session()
    ecs = session.client("ecs")
    resp = ecs.describe_capacity_providers(capacityProviders=[name])
    providers = resp.get("capacityProviders", [])
    if not providers:
        raise ValueError(f"CapacityProvider {name} not found")
    return providers[0]


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
    "targetgroup": fetch_target_group,
    "ecrrepository": fetch_ecr_repository,
    "secret": fetch_secret,
    "ssmparameter": fetch_ssm_parameter,
    "capacityprovider": fetch_capacity_provider,
}


_KIND_CANONICAL = {
    "taskdefinition": "TaskDefinition",
    "service": "Service",
    "cluster": "Cluster",
    "loadbalancer": "LoadBalancer",
    "autoscalinggroup": "AutoScalingGroup",
    "servicediscoverynamespace": "ServiceDiscoveryNamespace",
    "servicediscoveryservice": "ServiceDiscoveryService",
    "certificate": "Certificate",
    "iamrole": "IAMRole",
    "targetgroup": "TargetGroup",
    "ecrrepository": "ECRRepository",
    "secret": "Secret",
    "ssmparameter": "SSMParameter",
    "capacityprovider": "CapacityProvider",
}


def fetch_resource(kind: str, name: str, cluster: str = None, session=None) -> ECSResource:
    session = session or boto3.Session()
    kind_norm = kind.lower().replace("-", "").replace("_", "")
    fetcher = FETCHERS.get(kind_norm)
    if not fetcher:
        raise ValueError(f"Unknown resource kind: {kind}")

    if kind_norm == "service":
        raw = fetcher(cluster, name, session=session)
    else:
        raw = fetcher(name, session=session)

    canonical_kind = _KIND_CANONICAL.get(kind_norm, kind)
    clean = strip_readonly(canonical_kind, raw)
    return ECSResource(
        apiVersion="ecs/v1",
        kind=kind,
        metadata=Metadata(name=name, namespace=cluster),
        spec=clean,
    )
