KNOWN_TYPES = {
    "cluster", "service", "task", "taskdefinition", "loadbalancer",
    "targetgroup", "autoscalinggroup", "capacityprovider", "ecrrepository",
    "secret", "ssmparameter", "servicediscoverynamespace",
    "servicediscoveryservice", "certificate", "iamrole",
}

ALIASES = {
    "svc": "service",
    "td": "taskdefinition",
    "taskdef": "taskdefinition",
    "asg": "autoscalinggroup",
    "lb": "loadbalancer",
    "alb": "loadbalancer",
    "tg": "targetgroup",
    "cp": "capacityprovider",
    "ecr": "ecrrepository",
    "repo": "ecrrepository",
    "sec": "secret",
    "ssm": "ssmparameter",
    "param": "ssmparameter",
    "ns": "servicediscoverynamespace",
    "sdns": "servicediscoverynamespace",
    "sdsvc": "servicediscoveryservice",
    "cert": "certificate",
    "role": "iamrole",
}


def normalize_resource_type(raw):
    """Normalize resource type: lowercase, strip separators, handle plurals and aliases."""
    rt = raw.lower().replace("-", "").replace("_", "")
    if rt in ALIASES:
        return ALIASES[rt]
    if rt in KNOWN_TYPES:
        return rt
    if rt.endswith("ies"):
        singular = rt[:-3] + "y"
        if singular in KNOWN_TYPES:
            return singular
    if rt.endswith("s"):
        singular = rt[:-1]
        if singular in KNOWN_TYPES:
            return singular
        if singular in ALIASES:
            return ALIASES[singular]
    return rt
