# HANDOFF — ecsctl v2.1.0

Last updated: 2026-08-25

## Current State

ecsctl is a kubectl-style CLI for managing AWS ECS clusters. Version 2.1.0 is feature-complete for core operations: CRUD on 15 resource types (including container instances as "nodes"), debugging (logs/exec/events/top), deployment ops (deploy/rollback/restart/wait), diff, watch mode, short aliases, kubectl-style output formatting, enriched list columns, and concise summary views.

All 169 tests pass. Tool is installed editable (`pip install -e .`) and tested live against `sujyoti-prod` context (ap-south-1, profile: sujyoti, cluster: Sujyoti-EdTech-PROD-cluster).

## Completed Work

### Commands (17 total)
| Command | File | Status |
|---------|------|--------|
| `get` | cli.py | List/fetch any of 15 types, watch mode (-w), summary view for named resources |
| `describe` | cli.py | Detailed kubectl-describe style view, yaml/json/table output |
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
| `deploy` | commands/deploy.py | --image OR --task-definition, optional --wait |
| `wait` | commands/wait.py | Boto3 waiters (stable/inactive/running/stopped) |
| `diff` | commands/diff.py | Local YAML vs live, exit code 1 on changes |

### Resource Types (15)
| Type | Alias(es) | List | Fetch | Apply | Delete |
|------|-----------|------|-------|-------|--------|
| cluster | — | Y | Y | Y | Y |
| service | svc | Y | Y | Y | Y |
| task | — | Y | — | — | — |
| taskdefinition | td, taskdef | Y | Y | Y | Y |
| node | ci, instance, containerinstance | Y | Y | — | — |
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

### Output Formatting
- **kubectl-style plain tables**: UPPERCASE headers, space-padded columns, no borders
- **Enriched list columns**: All 15 listers show relevant details (not just names)
- **Summary view**: `get <type> <name>` shows concise human-readable summary (TD: family, revision, CPU, memory, containers, services using it)
- **Describe view**: kubectl-describe style nested Key: Value output with proper indentation
- **Deploy with --task-definition**: Deploy specific TD revision without needing --image

### Infrastructure Changes
- Lazy boto3 client initialization (executor.py)
- boto3.Session threaded from config context through entire codebase
- Resource type normalization with plural handling and aliases (types.py)
- Registry/dispatch patterns for list/fetch/apply instead of if/elif chains
- Extracted shared diff utilities (diff.py)
- Watch loop utility (watcher.py)
- CloudWatch Logs streaming generator (streaming.py)
- Lister registry (lister.py) with enriched columns for all types
- Summary module (summary.py) for concise single-resource views
- Output module (output.py) with kubectl-style formatting + print_describe()

## Architecture

```
ecsctl/
├── __init__.py          # __version__ = "2.1.0"
├── cli.py               # Click group + all top-level commands + command registration
├── types.py             # KNOWN_TYPES, ALIASES, normalize_resource_type()
├── config.py            # ConfigManager: contexts, get_session(), get_cluster()
├── executor.py          # AWSExecutor: lazy clients, dry-run, call()
├── applier.py           # HANDLERS dict -> apply_* functions (14 types)
├── fetcher.py           # FETCHERS dict -> fetch_* functions (15 types), READONLY_STRIPPERS
├── lister.py            # LISTERS dict -> list_* functions (15 types, enriched columns)
├── summary.py           # get_summary() — concise views for named resource get
├── editor.py            # edit_resource(): fetch -> tempfile -> $EDITOR -> diff -> apply
├── diff.py              # calculate_diff(), print_diff() (colored)
├── output.py            # OutputFormatter: table/json/yaml + print_describe()
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
    ├── deploy.py         # --image: clone TD + update + register + update svc; --task-definition: direct update
    ├── wait.py           # boto3 waiters wrapper
    └── diff.py           # load YAML -> fetch live -> calculate_diff -> print
```

## Important Decisions

1. **Session from context, not environment** — `config.get_session()` creates boto3.Session with profile_name/region_name from the active ecsctl context.

2. **Lazy client init** — Executor only creates boto3 clients when first accessed via `executor.client("service_name")`.

3. **normalize_resource_type in types.py** — Extracted to avoid circular imports. Handles: lowercase, strip `-_`, ALIASES lookup, KNOWN_TYPES check, `-ies` plural, `-s` plural.

4. **No VPC/Subnet/Route53/SNS/SQS/EventBridge/CloudWatch provisioning** — Excluded from scope.

5. **Tests mock boto3.Session** — conftest's `mock_boto3_clients` fixture patches both `boto3.client` AND `boto3.Session` to return fake clients.

6. **Read-only field stripping** — READONLY_STRIPPERS removes AWS-managed fields before presenting as declarative YAML. Enables clean round-trip: describe -> edit -> apply.

7. **kubectl-style output** — Plain tables with UPPERCASE headers, no borders. `get <name>` shows summary, `describe` shows nested key-value, `-oyaml`/`-ojson` for full spec.

8. **Node = Container Instance** — ECS container instances exposed as "node" (kubectl parity). Aliases: ci, instance, containerinstance.

9. **Deploy supports --task-definition** — For "edit TD then update service" workflow without changing image. Either `--image` or `--task-definition` required.

10. **Tags for task definitions** — `fetch_task_definition` uses `include=["TAGS"]` and merges `resp["tags"]` into TD dict (AWS returns tags at response top-level, not inside taskDefinition object).

## Files Changed (from v2.0.0)

New files:
- `ecsctl/types.py`
- `ecsctl/lister.py`
- `ecsctl/summary.py`
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
- `ecsctl/cli.py` (command registration, normalize import, EPILOG with aliases, watch flag, summary views, describe formatting)
- `ecsctl/config.py` (added get_session())
- `ecsctl/executor.py` (lazy client init, session param)
- `ecsctl/fetcher.py` (6 new fetchers incl. node, session fallback, new READONLY_STRIPPERS, include=["TAGS"] for TD)
- `ecsctl/applier.py` (5 new apply handlers, executor.client() calls)
- `ecsctl/output.py` (kubectl-style plain tables, print_describe(), _print_list_item())
- `ecsctl/editor.py` (imports from ecsctl.diff instead of inline)
- `setup.py` (version bump)
- `README.md` (full rewrite with node support)
- `tests/conftest.py` (boto3.Session patch in fixture)
- `tests/test_cli.py` (version assertion)
- `tests/test_cli_subcommands.py` (error message assertion, fetch_resource call signature)
- `tests/test_executor.py` (lazy init test)
- `tests/test_fetcher.py` (boto3.Session patch, include=["TAGS"] assertion)
- `tests/test_output.py` (UPPERCASE header assertion)

## Known Issues

1. **Pyright unresolved imports** — Pyright can't resolve `ecsctl.types`, `ecsctl.commands.*`, `ecsctl.watcher`, `ecsctl.lister`. False positives from editable install not in Pyright's search path. Runtime works fine.

2. **`logs` and `exec` require running tasks** — If ASG has 0 instances or service has 0 running tasks, these commands fail with "No tasks found".

3. **`top` shows N/A** — CloudWatch metrics only available when tasks have been running for 5+ minutes.

4. **Pagination not exhaustive** — Some listers don't handle nextToken for accounts with 100+ resources. Single page only.

5. **No tests for new commands** — The 9 command modules (logs, exec, events, top, rollback, restart, deploy, wait, diff) lack mocked test coverage. Tested live only.

6. **Node has no apply/delete** — Container instances are managed by ASG/capacity providers, not directly created/deleted.

## Next Tasks (Priority Order)

### High Priority
1. **Add tests for new commands** — Unit tests for all 9 command modules + summary.py + lister enrichments.
2. **Pagination support** — nextToken loop for all listers with 100+ item potential.
3. **Multi-file/directory apply** — `ecsctl apply -f ./manifests/` with kind priority sorting.

### Medium Priority
4. **Tab completion** — Click shell_complete for resource types + dynamic name completion.
5. **Manifest validation** — Required field checks per kind before sending to AWS.
6. **Port-forward command** — `ecsctl port-forward service/my-app 8080:80` via SSM.
7. **Multi-document YAML** — `---` separated documents via `yaml.safe_load_all()`.

### Low Priority
8. **Output column customization** — `-o custom-columns=NAME:.name,STATUS:.status`
9. **Resource filtering** — `--label-selector env=prod` or `--field-selector status=ACTIVE`
10. **Plugin system** — Custom resource types via entry_points.

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
Remote: `origin/main` (GitHub: awskrishnak/ecsctl)
