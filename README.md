# ecsctl

A kubectl-style CLI for managing AWS ECS clusters entirely from the command line. Manage services, task definitions, container instances (nodes), load balancers, auto scaling groups, ECR repositories, secrets, SSM parameters, certificates, IAM roles, and more using declarative YAML manifests.

## Why ecsctl

AWS ECS lacks a native CLI that treats infrastructure as declarative configuration. `ecsctl` closes that gap:

- **Declarative manifests** — Define your ECS stack in YAML and apply idempotently
- **Dry-run support** — Preview every AWS API call before execution
- **Live editing** — Fetch a resource, edit in `$EDITOR`, review diff, apply
- **Debugging** — Stream logs, exec into containers, view events, monitor utilization
- **Deployment ops** — Deploy images, rollback, restart, wait for stability
- **Context switching** — Operate across dev, staging, production clusters seamlessly
- **Short aliases** — `svc`, `td`, `asg`, `lb`, `ecr`, `cert`, `role`, etc.

## Requirements

- Python 3.8+
- AWS CLI configured with credentials (SSO or static keys)
- IAM permissions for: `ECS`, `EC2`, `ELBv2`, `AutoScaling`, `IAM`, `ACM`, `ServiceDiscovery`, `ECR`, `SecretsManager`, `SSM`, `CloudWatch Logs`
- `session-manager-plugin` (for `exec` command only)

## Installation

```bash
git clone https://github.com/awskrishnak/ecsctl.git
cd ecsctl
pip install -e .
```

Verify:
```bash
ecsctl --version
# ecsctl, version 2.1.0
```

## Quick Start

### 1. Configure a context

```bash
ecsctl config set prod --cluster-name production --aws-profile myprofile --aws-region us-east-1
ecsctl config context prod
```

### 2. List resources

```bash
ecsctl get svc
ecsctl get td
ecsctl get node
ecsctl get asg
ecsctl get ecr
```

### 3. Inspect a resource

```bash
ecsctl describe service my-api -o yaml
```

### 4. Deploy a new image

```bash
ecsctl deploy my-api --image myrepo/myapp:v2.0 --wait
```

### 5. Apply a manifest

```bash
ecsctl apply -f service.yaml --dry-run
ecsctl apply -f service.yaml
```

## Commands

| Command | Description |
|---------|-------------|
| `get` | List resources or get a specific resource by name |
| `describe` | Show detailed info for a named resource |
| `apply` | Create or update resources from YAML manifests |
| `delete` | Delete resources defined in YAML manifests |
| `edit` | Edit a live resource in $EDITOR, preview diff, apply |
| `diff` | Show differences between local YAML and live resource |
| `deploy` | Deploy a new image to a service |
| `rollback` | Roll back to a previous task definition revision |
| `restart` | Rolling restart (keeps current task definition) |
| `scale` | Scale a service to a desired task count |
| `run` | Run a one-off Fargate task from an image |
| `logs` | View/stream logs for a service or task |
| `exec` | Execute a command in a running container |
| `events` | Show service deployment events |
| `top` | Show CPU/memory utilization |
| `wait` | Wait for a resource to reach a condition |
| `config` | Manage configuration contexts |

## Resource Types

| Kind | Alias | AWS Service |
|------|-------|-------------|
| `service` | `svc` | ECS |
| `task` | — | ECS |
| `taskdefinition` | `td` | ECS |
| `cluster` | — | ECS |
| `node` | `ci`, `instance` | ECS (Container Instances) |
| `capacityprovider` | `cp` | ECS |
| `loadbalancer` | `lb`, `alb` | ELBv2 |
| `targetgroup` | `tg` | ELBv2 |
| `autoscalinggroup` | `asg` | Auto Scaling |
| `ecrrepository` | `ecr`, `repo` | ECR |
| `secret` | `sec` | Secrets Manager |
| `ssmparameter` | `ssm`, `param` | Systems Manager |
| `certificate` | `cert` | ACM |
| `iamrole` | `role` | IAM |
| `servicediscoverynamespace` | `ns` | Cloud Map |
| `servicediscoveryservice` | `sdsvc` | Cloud Map |

Plurals also work: `ecsctl get services`, `ecsctl get nodes`, `ecsctl get ecrrepositories`, etc.

## Configuration

Contexts stored in `~/.ecsctl/config.json`:

```bash
ecsctl config set dev  --cluster-name dev-cluster --aws-region us-east-1
ecsctl config set prod --cluster-name prod-cluster --aws-profile production --aws-region us-east-1

ecsctl config context prod    # switch active context
ecsctl config show --show-all # view all contexts
```

Environment variables override active context:

| Variable | Purpose |
|----------|---------|
| `AWS_ECS_CLUSTER_NAME` | Default cluster |
| `AWS_PROFILE` | AWS CLI profile |
| `AWS_DEFAULT_REGION` | AWS region |
| `EDITOR` | Editor for `edit` command |

## Usage Examples

### Listing and Inspecting

```bash
ecsctl get svc                          # list services (table)
ecsctl get td                           # list task definitions with details
ecsctl get node                         # list container instances (nodes)
ecsctl get td -o json                   # list task definitions (JSON)
ecsctl describe service my-api -o yaml  # full YAML spec
ecsctl get svc -w                       # watch mode (poll every 2s)
```

### Deploying and Managing

```bash
ecsctl deploy my-api --image repo:v2.0 --wait              # deploy new image, wait for stable
ecsctl deploy my-api --task-definition my-app:5 --wait     # deploy specific TD revision
ecsctl rollback my-api                                      # revert to previous task def revision
ecsctl rollback my-api --revision 3                         # revert to specific revision
ecsctl restart my-api                                       # force rolling restart
ecsctl scale my-api 5                                       # scale to 5 tasks
```

### Debugging

```bash
ecsctl logs my-api --follow --tail 100           # stream logs
ecsctl logs my-api --since 5m --timestamps       # recent logs with timestamps
ecsctl exec my-api --command /bin/sh             # shell into container
ecsctl events service my-api --watch             # watch deployment events
ecsctl top service                               # CPU/memory for all services
ecsctl top service my-api                        # CPU/memory for one service
```

### Manifests

```bash
ecsctl apply -f service.yaml --dry-run           # preview changes
ecsctl apply -f td.yaml -f service.yaml          # apply multiple files
ecsctl diff -f service.yaml                      # show drift from live
ecsctl delete -f service.yaml --dry-run          # preview deletion
```

### Waiting

```bash
ecsctl wait service my-api --for stable --timeout 300
ecsctl wait task abc123def --for stopped
```

### Editing Live Resources

```bash
ecsctl edit service my-api              # opens in $EDITOR, shows diff, confirms
ecsctl edit taskdefinition my-app:5     # edit task def (registers new revision)
```

## Architecture

```
User / CI
    |
    v
+-------------+
|   ecsctl    |  CLI (Click) + YAML + Diff + Streaming
|    CLI      |
+------+------+
       |
       v
+--------------+
| AWS Executor |  Lazy client init + dry-run logger
|  (boto3)     |
+------+-------+
       |
   +---+---+--------+--------+--------+--------+--------+
   v       v        v        v        v        v        v
  ECS    ELBv2   AutoScaling IAM     ACM      ECR    CloudWatch
                                              |        Logs
                                         Cloud Map
                                         Secrets Mgr
                                         SSM
```

### Module Layout

```
ecsctl/
├── __init__.py          # Version (2.1.0)
├── cli.py               # Click commands registration + shared options
├── types.py             # Resource type normalization + aliases
├── config.py            # Multi-context config manager (~/.ecsctl/config.json)
├── executor.py          # Lazy boto3 client wrapper with dry-run logging
├── applier.py           # Per-kind create-or-update handlers (14 types)
├── fetcher.py           # Read live AWS state, strip read-only fields
├── summary.py           # Concise summary views for get <type> <name>
├── lister.py            # Registry-based resource listing (15 types)
├── editor.py            # Fetch -> $EDITOR -> diff -> confirm -> apply
├── diff.py              # Shared diff calculation and colored output
├── output.py            # Table / JSON / YAML formatter
├── watcher.py           # Watch-mode polling loop
├── streaming.py         # CloudWatch Logs streaming generator
├── resources/
│   └── base.py          # ECSResource + Metadata dataclasses
└── commands/
    ├── __init__.py
    ├── logs.py           # Log viewing and streaming
    ├── exec.py           # Container exec via SSM
    ├── events.py         # Service event viewer
    ├── top.py            # CPU/memory utilization
    ├── rollback.py       # Task definition rollback
    ├── restart.py        # Force new deployment
    ├── deploy.py         # Image deployment workflow
    ├── wait.py           # Boto3 waiter wrappers
    └── diff.py           # Local vs live diff
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

- **Task Definitions are immutable.** `apply` always registers a new revision.
- **Lazy client initialization.** boto3 clients created on first use, not at startup.
- **Session from context.** AWS profile/region resolved from active ecsctl context automatically.
- **ALBs are mostly immutable.** `apply` creates if missing; listener changes handled separately.
- **IAM Roles support policy sync.** Diffs managed policy attachments and inline policies.
- **Certificates cannot be edited.** `apply` requests new only if domain doesn't have one.

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| `Cluster required` | Set via `--cluster`, context, or `AWS_ECS_CLUSTER_NAME` |
| `No tasks found` | Service has 0 running tasks (check ASG capacity) |
| `session-manager-plugin not found` | Install AWS Session Manager Plugin for `exec` |
| `Access denied` | Confirm IAM permissions for the target service |
| `Unknown resource type` | Check `ecsctl --help` for supported types and aliases |
| `Dry-run shows no output` | Verify manifest `kind` is supported and file exists |

## Testing

**169 tests, ~94% coverage.**

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=ecsctl --cov-report=term-missing

# Single file
pytest tests/test_cli_subcommands.py -v
```

### Test Dependencies

```bash
pip install pytest pytest-mock pytest-cov moto
```

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures (mock clients, sample YAML)
├── fixtures/
│   └── aws_responses.py         # AWS skeleton-based response fixtures
├── test_resources_base.py       # ECSResource model (16 tests)
├── test_config.py               # ConfigManager (12 tests)
├── test_executor.py             # AWSExecutor dry-run & lazy init (8 tests)
├── test_applier.py              # All apply handlers (30 tests)
├── test_fetcher.py              # All fetch functions & stripping (25 tests)
├── test_editor.py               # Diff calculation (5 tests)
├── test_output.py               # Formatting (12 tests)
├── test_cli.py                  # CLI integration (14 tests)
└── test_cli_subcommands.py      # Full subcommand validation (47 tests)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/description`)
3. Commit your changes (`git commit -m "feat: description"`)
4. Push to the branch (`git push origin feature/description`)
5. Open a Pull Request

Please include tests for new resource kinds or apply logic.

## License

MIT
