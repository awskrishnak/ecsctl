# ecsctl

A command-line interface for AWS ECS that behaves like `kubectl`. Manage Task Definitions, Services, Load Balancers, Auto Scaling Groups, IAM Roles, ACM Certificates, and Service Discovery resources using declarative YAML manifests.

## Why ecsctl

AWS ECS lacks a native CLI that treats infrastructure as declarative configuration. `ecsctl` closes that gap by providing:

- **Declarative manifests**: Define your entire ECS stack in YAML and apply it idempotently.
- **Dry-run support**: Preview every AWS API call before execution.
- **Live editing**: Fetch a resource, edit it in your `$EDITOR`, review a diff, and apply.
- **Multi-resource orchestration**: Manage ECS, ELB, Auto Scaling, IAM, ACM, and Cloud Map from one tool.
- **Context switching**: Seamlessly operate across dev, staging, and production clusters.

## Requirements

- Python 3.8+
- AWS CLI configured with credentials
- IAM permissions for: `ECS`, `EC2`, `ElasticLoadBalancing`, `AutoScaling`, `IAM`, `ACM`, `ServiceDiscovery`

## Installation

```bash
git clone https://github.com/10clouds/ecsctl.git
cd ecsctl
pip install -e .
```

## Quick Start

### 1. Configure a context

```bash
ecsctl config set prod   --cluster-name production   --aws-profile default   --aws-region us-east-1

ecsctl config context prod
```

### 2. Apply a manifest

```bash
ecsctl apply -f examples/service.yaml --dry-run
ecsctl apply -f examples/service.yaml
```

### 3. Inspect resources

```bash
ecsctl get services
ecsctl describe service my-api -o yaml
```

## Configuration

Contexts are stored in `~/.ecsctl/config.json`. You can define multiple clusters and switch between them.

```bash
ecsctl config set dev  --cluster-name dev  --aws-region us-east-1
ecsctl config set prod --cluster-name prod --aws-region us-east-1

ecsctl config context prod
ecsctl config show --show-all
```

Environment variables override the active context:

| Variable | Purpose |
|----------|---------|
| `AWS_ECS_CLUSTER_NAME` | Default cluster |
| `AWS_PROFILE` | AWS CLI profile |
| `AWS_DEFAULT_REGION` | AWS region |
| `EDITOR` | Editor for the `edit` command |

## Usage

### apply

Create or update resources from YAML manifests.

```bash
ecsctl apply -f task-definition.yaml
ecsctl apply -f task-definition.yaml -f service.yaml
ecsctl apply -f infra/ --dry-run
```

### get / describe

List and inspect resources. Output formats: `table` (default), `json`, `yaml`.

```bash
ecsctl get services
ecsctl get service my-api -o yaml
ecsctl describe service my-api -o yaml
ecsctl get loadbalancers
ecsctl get autoscalinggroups
ecsctl get certificates
ecsctl get iamroles
```

### edit

Fetch a live resource, open it in `$EDITOR`, review the diff, and apply.

```bash
ecsctl edit service my-api
ecsctl edit loadbalancer api-alb
ecsctl edit iamrole ecsTaskRole --dry-run
```

### delete

Remove resources defined in YAML files.

```bash
ecsctl delete -f service.yaml --dry-run
ecsctl delete -f service.yaml
```

### scale

```bash
ecsctl scale my-api 5 --dry-run
ecsctl scale my-api 5
```

## Supported Resources

| Kind | AWS Service | Notes |
|------|-------------|-------|
| `TaskDefinition` | ECS | Immutable; apply registers a new revision |
| `Service` | ECS | Auto-detects create vs. update |
| `Cluster` | ECS | Create or update settings |
| `Task` | ECS | One-off execution |
| `LoadBalancer` | ELBv2 | ALB / NLB |
| `AutoScalingGroup` | Auto Scaling | EC2 capacity management |
| `ServiceDiscoveryNamespace` | Cloud Map | Private / Public DNS |
| `ServiceDiscoveryService` | Cloud Map | Service registry |
| `Certificate` | ACM | Request or import SSL certs |
| `IAMRole` | IAM | Syncs managed and inline policies |

## Architecture

```
User / CI
    │
    ▼
┌─────────────┐
│   ecsctl    │  CLI (Click) + YAML Parser + Diff Engine
│    CLI      │
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ AWS Executor │  Dry-run logger + boto3 multi-service client
│  (boto3)     │
└──────┬───────┘
       │
   ┌───┴───┬────────┬────────┬────────┐
   ▼       ▼        ▼        ▼        ▼
  ECS    ELBv2   AutoScaling  IAM     ACM
                              │
                         Cloud Map
```

## Examples

See [`examples/`](examples/) for complete YAML manifests:

- [`task-definition.yaml`](examples/task-definition.yaml) — Fargate task with CloudWatch logging
- [`service.yaml`](examples/service.yaml) — ECS service with awsvpc networking
- [`alb.yaml`](examples/alb.yaml) — Internet-facing application load balancer
- [`asg.yaml`](examples/asg.yaml) — Auto Scaling Group for EC2 capacity
- [`cloudmap.yaml`](examples/cloudmap.yaml) — Private DNS namespace and service discovery
- [`acm.yaml`](examples/acm.yaml) — SSL certificate request
- [`iam-role.yaml`](examples/iam-role.yaml) — Task role with inline and managed policies

## Design Decisions

- **Task Definitions are immutable.** `apply` always registers a new revision. Services referencing the task definition are updated automatically when applied via a Service manifest.
- **ALBs are mostly immutable.** `apply` creates the load balancer if it does not exist. Listener and target group changes are handled separately.
- **IAM Roles support policy synchronization.** `apply` diffs managed policy attachments and inline policies, adding or removing them as needed.
- **Certificates cannot be edited.** `apply` requests a new certificate only if one for the domain does not already exist.

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| `Cluster not found` | Verify `AWS_ECS_CLUSTER_NAME` or `--cluster` is set correctly |
| `Task definition not found` | Ensure the task definition family name matches exactly |
| `Access denied` | Confirm IAM user/role has the required service permissions |
| `Dry-run shows no output` | Check that the manifest `kind` is supported and the file path is correct |
| `Edit shows no changes` | The fetched spec may contain read-only fields that were stripped; only mutable fields trigger a diff |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/description`)
3. Commit your changes (`git commit -m "feat: description"`)
4. Push to the branch (`git push origin feature/description`)
5. Open a Pull Request

Please include tests for new resource kinds or apply logic.

## License

MIT

