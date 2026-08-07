import json
from typing import Any
from ecsctl.resources.base import ECSResource
from ecsctl.executor import AWSExecutor


def _convert_tags(tags):
    if not tags:
        return []
    if isinstance(tags, dict):
        return [{"Key": k, "Value": v} for k, v in tags.items()]
    if isinstance(tags, list) and tags and isinstance(tags[0], dict):
        if "Key" in tags[0]:
            return tags
    return []


def apply_task_definition(spec: dict, executor: AWSExecutor) -> Any:
    return executor.call("ecs", "register_task_definition", spec)


def apply_service(name: str, spec: dict, executor: AWSExecutor, cluster: str) -> Any:
    ecs = executor.clients["ecs"]
    try:
        resp = ecs.describe_services(cluster=cluster, services=[name])
        if resp["services"] and resp["services"][0]["status"] != "INACTIVE":
            update_params = {"cluster": cluster, "service": name}
            allowed = [
                "taskDefinition", "desiredCount", "forceNewDeployment",
                "placementStrategy", "placementConstraints", "platformVersion",
                "healthCheckGracePeriodSeconds", "networkConfiguration",
                "deploymentConfiguration",
            ]
            for k in allowed:
                if k in spec:
                    update_params[k] = spec[k]
            return executor.call("ecs", "update_service", update_params)
    except Exception:
        pass
    create_params = {"cluster": cluster, "serviceName": name, **spec}
    return executor.call("ecs", "create_service", create_params)


def apply_cluster(name: str, spec: dict, executor: AWSExecutor) -> Any:
    ecs = executor.clients["ecs"]
    try:
        ecs.describe_clusters(clusters=[name])
        if "settings" in spec:
            return executor.call("ecs", "put_cluster_settings", {
                "cluster": name,
                "settings": spec["settings"],
            })
        return {"message": f"Cluster {name} already exists"}
    except Exception:
        pass
    return executor.call("ecs", "create_cluster", {"clusterName": name, **spec})


def apply_asg(name: str, spec: dict, executor: AWSExecutor) -> Any:
    autoscaling = executor.clients["autoscaling"]
    try:
        resp = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
        if resp.get("AutoScalingGroups"):
            update_params = {"AutoScalingGroupName": name}
            for k in ["MinSize", "MaxSize", "DesiredCapacity", "DefaultCooldown",
                      "AvailabilityZones", "HealthCheckType", "HealthCheckGracePeriod",
                      "VPCZoneIdentifier", "TerminationPolicies"]:
                for kk in spec:
                    if kk.lower() == k.lower():
                        update_params[k] = spec[kk]
            return executor.call("autoscaling", "update_auto_scaling_group", update_params)
    except Exception:
        pass
    create_params = {**spec, "AutoScalingGroupName": name}
    return executor.call("autoscaling", "create_auto_scaling_group", create_params)


def apply_alb(name: str, spec: dict, executor: AWSExecutor) -> Any:
    elbv2 = executor.clients["elbv2"]
    try:
        resp = elbv2.describe_load_balancers(Names=[name])
        if resp.get("LoadBalancers"):
            return {"message": f"ALB {name} exists. Listener updates not yet supported via apply."}
    except Exception:
        pass
    create_params = {
        "Name": name,
        "Subnets": spec.get("subnets", spec.get("Subnets")),
        "SecurityGroups": spec.get("securityGroups", spec.get("SecurityGroups")),
        "Scheme": spec.get("scheme", spec.get("Scheme", "internet-facing")),
        "Type": spec.get("type", spec.get("Type", "application")),
        "Tags": _convert_tags(spec.get("tags", spec.get("Tags"))),
    }
    return executor.call("elbv2", "create_load_balancer", create_params)


def apply_sd_namespace(name: str, spec: dict, executor: AWSExecutor) -> Any:
    sd = executor.clients["servicediscovery"]
    try:
        resp = sd.list_namespaces()
        for ns in resp.get("Namespaces", []):
            if ns["Name"] == name:
                return {"message": f"Namespace {name} already exists"}
    except Exception:
        pass
    ns_type = spec.get("type", "DNS_PRIVATE")
    if ns_type == "DNS_PRIVATE":
        params = {
            "Name": name,
            "Description": spec.get("description", ""),
            "Vpc": spec.get("vpcId"),
        }
        return executor.call("servicediscovery", "create_private_dns_namespace", params)
    else:
        params = {"Name": name, "Description": spec.get("description", "")}
        return executor.call("servicediscovery", "create_public_dns_namespace", params)


def apply_sd_service(name: str, spec: dict, executor: AWSExecutor) -> Any:
    sd = executor.clients["servicediscovery"]
    try:
        resp = sd.list_services()
        for svc in resp.get("Services", []):
            if svc["Name"] == name:
                return executor.call("servicediscovery", "update_service", {
                    "Id": svc["Id"],
                    **spec,
                })
    except Exception:
        pass
    return executor.call("servicediscovery", "create_service", {"Name": name, **spec})


def apply_certificate(name: str, spec: dict, executor: AWSExecutor) -> Any:
    acm = executor.clients["acm"]
    certs = acm.list_certificates().get("CertificateSummaryList", [])
    for c in certs:
        if c.get("DomainName") == spec.get("domainName"):
            return {"message": f"Certificate for {spec['domainName']} already exists", "arn": c["CertificateArn"]}
    return executor.call("acm", "request_certificate", {
        "DomainName": spec["domainName"],
        "SubjectAlternativeNames": spec.get("subjectAlternativeNames", []),
        "ValidationMethod": spec.get("validationMethod", "DNS"),
        "Tags": _convert_tags(spec.get("tags", [])),
    })


def apply_iam_role(name: str, spec: dict, executor: AWSExecutor) -> Any:
    iam = executor.clients["iam"]
    assume_doc = spec.get("assumeRolePolicyDocument")
    if isinstance(assume_doc, dict):
        assume_doc = json.dumps(assume_doc)

    try:
        iam.get_role(RoleName=name)
        if assume_doc:
            executor.call("iam", "update_assume_role_policy", {
                "RoleName": name,
                "PolicyDocument": assume_doc,
            })
        current = iam.list_attached_role_policies(RoleName=name).get("AttachedPolicies", [])
        current_arns = {p["PolicyArn"] for p in current}
        desired_arns = set(spec.get("managedPolicyArns", []))
        for arn in desired_arns - current_arns:
            executor.call("iam", "attach_role_policy", {"RoleName": name, "PolicyArn": arn})
        for arn in current_arns - desired_arns:
            executor.call("iam", "detach_role_policy", {"RoleName": name, "PolicyArn": arn})

        current_inline = set(iam.list_role_policies(RoleName=name).get("PolicyNames", []))
        desired_inline = {p["PolicyName"] for p in spec.get("inlinePolicies", [])}
        for pol_name in current_inline - desired_inline:
            executor.call("iam", "delete_role_policy", {"RoleName": name, "PolicyName": pol_name})
        for pol in spec.get("inlinePolicies", []):
            doc = pol["PolicyDocument"]
            if isinstance(doc, dict):
                doc = json.dumps(doc)
            executor.call("iam", "put_role_policy", {
                "RoleName": name,
                "PolicyName": pol["PolicyName"],
                "PolicyDocument": doc,
            })
        return {"message": f"IAM Role {name} updated"}
    except iam.exceptions.NoSuchEntityException:
        executor.call("iam", "create_role", {
            "RoleName": name,
            "AssumeRolePolicyDocument": assume_doc,
            "Tags": _convert_tags(spec.get("tags", [])),
        })
        for arn in spec.get("managedPolicyArns", []):
            executor.call("iam", "attach_role_policy", {"RoleName": name, "PolicyArn": arn})
        for pol in spec.get("inlinePolicies", []):
            doc = pol["PolicyDocument"]
            if isinstance(doc, dict):
                doc = json.dumps(doc)
            executor.call("iam", "put_role_policy", {
                "RoleName": name,
                "PolicyName": pol["PolicyName"],
                "PolicyDocument": doc,
            })
        return {"message": f"IAM Role {name} created"}


HANDLERS = {
    "taskdefinition": lambda r, e, c: apply_task_definition(r.spec, e),
    "service": lambda r, e, c: apply_service(r.metadata.name, r.spec, e, c),
    "cluster": lambda r, e, c: apply_cluster(r.metadata.name, r.spec, e),
    "autoscalinggroup": lambda r, e, c: apply_asg(r.metadata.name, r.spec, e),
    "loadbalancer": lambda r, e, c: apply_alb(r.metadata.name, r.spec, e),
    "servicediscoverynamespace": lambda r, e, c: apply_sd_namespace(r.metadata.name, r.spec, e),
    "servicediscoveryservice": lambda r, e, c: apply_sd_service(r.metadata.name, r.spec, e),
    "certificate": lambda r, e, c: apply_certificate(r.metadata.name, r.spec, e),
    "iamrole": lambda r, e, c: apply_iam_role(r.metadata.name, r.spec, e),
}


def apply_resource(resource: ECSResource, executor: AWSExecutor, cluster: str = None) -> Any:
    kind = resource.kind.lower().replace("-", "").replace("_", "")
    handler = HANDLERS.get(kind)
    if not handler:
        raise ValueError(f"Unknown resource kind for apply: {resource.kind}")
    return handler(resource, executor, cluster)
