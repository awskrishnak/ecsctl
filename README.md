# ecsctl v2.0

A **kubectl-style** CLI for managing AWS ECS clusters and supporting infrastructure resources.

## Features

- **Declarative YAML manifests** for ECS and AWS resources
- `apply -f`, `delete -f` with `--dry-run` support
- `edit` command with diff preview before applying
- `-o yaml / -o json` output for all `get` and `describe` commands
- Multi-resource support:
  - ECS: TaskDefinition, Service, Cluster, Task
  - Infrastructure: LoadBalancer (ALB), AutoScalingGroup
  - Discovery: ServiceDiscoveryNamespace, ServiceDiscoveryService
  - Security: Certificate (ACM), IAMRole

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Set your cluster
export AWS_ECS_CLUSTER_NAME=my-cluster

# Apply a service manifest
ecsctl apply -f examples/service.yaml --dry-run
ecsctl apply -f examples/service.yaml

# Edit a live resource
ecsctl edit service my-api

# Get resource as YAML
ecsctl get service my-api -o yaml
ecsctl get loadbalancer -o yaml

# Scale a service
ecsctl scale my-api 5 --dry-run
ecsctl scale my-api 5
```

## Configuration Contexts

```bash
ecsctl config set prod --cluster-name production --aws-region us-east-1
ecsctl config context prod
ecsctl config show --show-all
```

## Resource YAML Examples

See the `examples/` directory for sample manifests:
- `task-definition.yaml`
- `service.yaml`
- `alb.yaml`
- `asg.yaml`
- `cloudmap.yaml`
- `acm.yaml`
- `iam-role.yaml`

## Notes

- **Task Definitions** are immutable in AWS. `apply` always registers a new revision.
- **ALBs** cannot change subnets or scheme after creation; `apply` will create or skip.
- **IAM Roles** support sync of managed and inline policies during updates.
- **Certificates** cannot be edited after creation; `apply` requests new if not found.
- Always use `--dry-run` first to preview changes.
