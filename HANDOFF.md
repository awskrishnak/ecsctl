# HANDOFF — ecsctl v2.1.0

Last updated: 2026-08-25

## Current State

ecsctl is a kubectl-style CLI for managing AWS ECS clusters. Version 2.1.0 is feature-complete for core operations: CRUD on 14 resource types, debugging (logs/exec/events/top), deployment ops (deploy/rollback/restart/wait), diff, watch mode, and short aliases.

All 169 tests pass. Tool is installed editable (`pip install -e .`) and tested live against `sujyoti-prod` context (ap-south-1, profile: sujyoti, cluster: Sujyoti-EdTech-PROD-cluster).

## Completed Work

### Commands (17 total)
| Command | File | Status |
|---------|------|--------|
| `get` | cli.py | List/fetch any of 14 types, watch mode (-w) |
| `describe` | cli.py | Detailed view, yaml/json/table output |
| `apply` | cli.py | Create-or-update from YAML, dry-run |
| `delete` | cli.py | Delete from YAML manifest, dry-run |
| `edit` | cli.py | $EDITOR workflow with diff preview |
| `scale` | cli.py | Set desired count |
| `run` | cli.py | One-off Fargate task |
| `config` | cli.py | set/show/context subcommands |
| `logs` | commands/logs.py | --follow, --tail, --since, --container, --timestamps |
| `exec` | commands/exec.py | SSM session-manager-plugin based |
| `events` | commands/events.py | Service events, --watch |
| `top` | commands/top.py | CloudWatch CPU/memory metrics |
| `rollback` | commands/rollback.py | Previous or specific revision |
| `restart` | commands/restart.py | forceNewDeployment |
| `deploy` | commands/deploy.py | New image + optional --wait |
| `wait` | commands/wait.py | Boto3 waiters (stable/inactive/running/stopped) |
| `diff` | commands/diff.py | Local YAML vs live, exit code 1 on changes |

### Resource Types (14)
| Type | Alias(es) | List | Fetch | Apply | Delete |
|------|-----------|------|-------|-------|--------|
| cluster | — | Y | Y | Y | Y |
| service | svc | Y | Y | Y | Y |
| task | — | Y | — | — | — |
| taskdefinition | td, taskdef | Y | Y | Y | Y |
| loadbalancer | lb, alb | Y | Y | Y | Y |
| targetgroup | tg | Y | Y | Y | Y |
| autoscalinggroup | asg | Y | Y | Y | Y |
| capacityprovider | cp | Y | Y | Y | Y |
| ecrrepository | ecr, repo | Y | Y | Y | Y |
| secret | sec | Y | Y | Y | Y |
| ssmparameter | ssm, param | Y | Y | Y | Y |
| servicediscoverynamespace | ns, sdns | Y | Y | Y | Y |
| servicediscoveryservice | sdsvc | Y | Y | Y | Y |
| certificate | cert | Y | Y | Y | Y |
| iamrole | role | Y | Y | Y | Y |

### Infrastructure Changes
- Lazy boto3 client initialization (executor.py)
- boto3.Session threaded from config context through entire codebase
- Resource type normalization with plural handling and aliases (types.py)
- Registry/dispatch patterns for list/fetch/apply instead of if/elif chains
- Extracted shared diff utilities (diff.py)
- Watch loop utility (watcher.py)
- CloudWatch Logs streaming generator (streaming.py)
- Lister registry (lister.py)

## Architecture

```
ecsctl/
├── __init__.py          # __version__ = "2.1.0"
├── cli.py               # Click group + all top-level commands + command registration
├── types.py             # KNOWN_TYPES, ALIASES, normalize_resource_type()
├── config.py            # ConfigManager: contexts, get_session(), get_cluster()
├── executor.py          # AWSExecutor: lazy clients, dry-run, call()
├── applier.py           # HANDLERS dict -> apply_* functions (14 types)
├── fetcher.py           # FETCHERS dict -> fetch_* functions, READONLY_STRIPPERS
├── lister.py            # LISTERS dict -> list_* functions (14 types)
├── editor.py            # edit_resource(): fetch -> tempfile -> $EDITOR -> diff -> apply
├── diff.py              # calculate_diff(), print_diff() (colored)
├── output.py            # OutputFormatter: table/json/yaml
├── watcher.py           # watch_loop(fn, interval)
├── streaming.py         # stream_log_events() generator
├── resources/
│   └── base.py          # ECSResource, Metadata dataclasses, from_yaml(), to_dict()
└── commands/
    ├── __init__.py
    ├── logs.py           # resolves service -> task def -> log config -> stream
    ├── exec.py           # resolves target -> execute_command -> session-manager-plugin
    ├── events.py         # describe_services -> events list
    ├── top.py            # CloudWatch get_metric_statistics
    ├── rollback.py       # find previous revision -> update_service
    ├── restart.py        # update_service(forceNewDeployment=True)
    ├── deploy.py         # clone task def -> update image -> register -> update service
    ├── wait.py           # boto3 waiters wrapper
    └── diff.py           # load YAML -> fetch live -> calculate_diff -> print
```

## Important Decisions

1. **Session from context, not environment** — `config.get_session()` creates boto3.Session with profile_name/region_name from the active ecsctl context. This means `ecsctl` respects its own context config rather than relying solely on AWS env vars.

2. **Lazy client init** — Executor only creates boto3 clients when first accessed via `executor.client("service_name")`. Previous eager init created all clients on startup.

3. **normalize_resource_type in types.py** — Extracted to avoid circular imports (cli.py imports commands, commands can't import cli.py). Handles: lowercase, strip `-_`, ALIASES lookup, KNOWN_TYPES check, `-ies` plural, `-s` plural.

4. **No VPC/Subnet/Route53/SNS/SQS/EventBridge/CloudWatch provisioning** — User explicitly excluded these from scope.

5. **Tests mock boto3.Session** — conftest's `mock_boto3_clients` fixture patches both `boto3.client` AND `boto3.Session` to return fake clients. Tests that directly call fetch functions use the `boto3.Session` patch (fetcher functions fall back to `boto3.Session()` when session=None).

6. **Read-only field stripping** — READONLY_STRIPPERS in fetcher.py removes AWS-managed fields before presenting resources as declarative YAML. This enables clean round-trip: describe -> edit -> apply.

## Files Changed (from v2.0.0)

New files:
- `ecsctl/types.py`
- `ecsctl/lister.py`
- `ecsctl/diff.py`
- `ecsctl/streaming.py`
- `ecsctl/watcher.py`
- `ecsctl/commands/__init__.py`
- `ecsctl/commands/logs.py`
- `ecsctl/commands/exec.py`
- `ecsctl/commands/events.py`
- `ecsctl/commands/top.py`
- `ecsctl/commands/rollback.py`
- `ecsctl/commands/restart.py`
- `ecsctl/commands/deploy.py`
- `ecsctl/commands/wait.py`
- `ecsctl/commands/diff.py`

Modified files:
- `ecsctl/__init__.py` (version bump 2.0.0 -> 2.1.0)
- `ecsctl/cli.py` (command registration, normalize import, EPILOG with aliases, watch flag)
- `ecsctl/config.py` (added get_session())
- `ecsctl/executor.py` (lazy client init, session param)
- `ecsctl/fetcher.py` (5 new fetchers, session fallback, new READONLY_STRIPPERS)
- `ecsctl/applier.py` (5 new apply handlers, executor.client() calls)
- `ecsctl/editor.py` (imports from ecsctl.diff instead of inline)
- `setup.py` (version bump)
- `README.md` (full rewrite)
- `tests/conftest.py` (boto3.Session patch in fixture)
- `tests/test_cli.py` (version assertion)
- `tests/test_cli_subcommands.py` (error message assertion, fetch_resource call signature)
- `tests/test_executor.py` (lazy init test)
- `tests/test_fetcher.py` (boto3.Session patch instead of boto3.client)

## Known Issues

1. **Pyright unresolved imports** — Pyright can't resolve `ecsctl.types`, `ecsctl.commands.*`, `ecsctl.watcher`, `ecsctl.lister`. These are false positives from editable install not being in Pyright's search path. Runtime works fine.

2. **`logs` and `exec` require running tasks** — If ASG has 0 instances or service has 0 running tasks, these commands fail with "No tasks found". This is correct behavior but could have a friendlier message suggesting to check capacity.

3. **`top` shows N/A** — CloudWatch metrics are only available when tasks have been running for 5+ minutes. No data = N/A in output.

4. **Pagination not exhaustive** — Some listers (list_services, list_tasks) don't handle nextToken for accounts with 100+ resources. Single page only.

5. **`events` and `top` commands** — Only support `service` (and `task` for top) resource types. Other types have no event concept in ECS.

6. **No tests for new commands** — The 9 new command modules (logs, exec, events, top, rollback, restart, deploy, wait, diff) don't have dedicated unit tests yet. They were tested live but lack mocked test coverage.

## Next Tasks (Priority Order)

### High Priority
1. **Add tests for new commands** — Unit tests for all 9 command modules. Mock boto3 calls, test dry-run paths, error cases. Would bring coverage from 94% to ~98%.

2. **Pagination support** — Add nextToken loop to all listers that can return 100+ items (services, tasks, IAM roles, secrets, SSM parameters).

3. **Multi-file/directory apply** — `ecsctl apply -f ./manifests/` to apply all YAML in a directory. Sort by kind priority (cluster first, services last).

### Medium Priority
4. **Tab completion** — Click shell_complete for resource types + dynamic name completion from AWS.

5. **Manifest validation** — Required field checks per kind before sending to AWS. Better error messages than raw boto3 exceptions.

6. **Port-forward command** — `ecsctl port-forward service/my-app 8080:80` using SSM StartPortForwardingSessionToRemoteHost.

7. **Multi-document YAML** — Support `---` separated documents in a single file via `yaml.safe_load_all()`.

### Low Priority
8. **Output column customization** — `ecsctl get svc -o custom-columns=NAME:.name,STATUS:.status`

9. **Resource filtering** — `ecsctl get svc --label-selector env=prod` or `--field-selector status=ACTIVE`

10. **Plugin system** — Allow custom resource types via entry_points.

## Config State

Active context: `sujyoti-prod`
```json
{
  "current": "sujyoti-prod",
  "contexts": {
    "dev": {"cluster_name": "dev-cluster", "aws_region": "us-east-1"},
    "prod": {"cluster_name": "prod-cluster", "aws_profile": "production-profile", "aws_region": "us-east-1"},
    "sujyoti-prod": {"cluster_name": "Sujyoti-EdTech-PROD-cluster", "aws_profile": "sujyoti", "aws_region": "ap-south-1"}
  }
}
```

## Git State

Branch: `main`
Latest commit: `2c3910d` — feat: add debugging commands, deployment ops, resource aliases, and 5 new resource types
Remote: `origin/main` (up to date)
