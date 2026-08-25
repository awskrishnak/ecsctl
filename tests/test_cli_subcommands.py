"""
Comprehensive validation of every ecsctl CLI subcommand.
Each test exercises the full path: CLI → parsing → executor → boto3 mock.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from ecsctl.cli import cli
from tests.fixtures.aws_responses import *


@pytest.fixture
def runner():
    return CliRunner()



# =============================================================================
# APPLY SUBCOMMAND - all resource kinds
# =============================================================================

class TestApplyAllKinds:
    """Validate `ecsctl apply -f <file>` for every supported resource kind."""

    def test_apply_service_creates(self, runner, sample_service_yaml, mock_boto3_clients):
        """apply Service → describe_services (check exists) → create_service."""
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_EMPTY
        mock_boto3_clients["ecs"].create_service.return_value = {"service": {"serviceName": "my-app-service"}}

        result = runner.invoke(cli, ["apply", "-f", sample_service_yaml, "--cluster", "production"])
        assert result.exit_code == 0
        assert "Applying Service/my-app-service" in result.output
        mock_boto3_clients["ecs"].create_service.assert_called_once()
        args = mock_boto3_clients["ecs"].create_service.call_args[1]
        assert args["cluster"] == "production"
        assert args["serviceName"] == "my-app-service"
        assert args["taskDefinition"] == "my-app"
        assert args["desiredCount"] == 2


    def test_apply_service_updates(self, runner, sample_service_yaml, mock_boto3_clients):
        """apply Service → describe_services (exists, ACTIVE) → update_service."""
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_RESPONSE
        mock_boto3_clients["ecs"].update_service.return_value = {"service": {"serviceName": "my-app-service"}}

        result = runner.invoke(cli, ["apply", "-f", sample_service_yaml, "--cluster", "production"])
        assert result.exit_code == 0
        mock_boto3_clients["ecs"].update_service.assert_called_once()
        args = mock_boto3_clients["ecs"].update_service.call_args[1]
        assert args["service"] == "my-app-service"
        assert args["cluster"] == "production"
        # Only allowed fields should pass through
        assert "launchType" not in args

    def test_apply_task_definition(self, runner, sample_task_definition_yaml, mock_boto3_clients):
        """apply TaskDefinition → register_task_definition."""
        mock_boto3_clients["ecs"].register_task_definition.return_value = REGISTER_TASK_DEFINITION_RESPONSE

        result = runner.invoke(cli, ["apply", "-f", sample_task_definition_yaml])
        assert result.exit_code == 0
        assert "Applying TaskDefinition/my-app" in result.output
        mock_boto3_clients["ecs"].register_task_definition.assert_called_once()
        args = mock_boto3_clients["ecs"].register_task_definition.call_args[1]
        assert args["family"] == "my-app"
        assert args["cpu"] == "256"
        assert args["memory"] == "512"
        assert args["networkMode"] == "awsvpc"
        assert len(args["containerDefinitions"]) == 1
        assert args["containerDefinitions"][0]["name"] == "app"
        assert args["containerDefinitions"][0]["image"] == "nginx:latest"


    def test_apply_alb_creates(self, runner, sample_alb_yaml, mock_boto3_clients):
        """apply LoadBalancer → describe (not found) → create_load_balancer."""
        mock_boto3_clients["elbv2"].describe_load_balancers.side_effect = Exception("Not found")
        mock_boto3_clients["elbv2"].create_load_balancer.return_value = {"LoadBalancers": [{"LoadBalancerArn": "arn:..."}]}

        result = runner.invoke(cli, ["apply", "-f", sample_alb_yaml])
        assert result.exit_code == 0
        assert "Applying LoadBalancer/api-alb" in result.output
        mock_boto3_clients["elbv2"].create_load_balancer.assert_called_once()
        args = mock_boto3_clients["elbv2"].create_load_balancer.call_args[1]
        assert args["Name"] == "api-alb"
        assert args["Subnets"] == ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
        assert args["SecurityGroups"] == ["sg-0123456789abcdef0"]
        assert args["Scheme"] == "internet-facing"
        assert args["Type"] == "application"
        # Tags dict → Key/Value list conversion
        assert {"Key": "Environment", "Value": "production"} in args["Tags"]

    def test_apply_asg_creates(self, runner, sample_asg_yaml, mock_boto3_clients):
        """apply AutoScalingGroup → describe (empty) → create."""
        mock_boto3_clients["autoscaling"].describe_auto_scaling_groups.return_value = DESCRIBE_AUTO_SCALING_GROUPS_EMPTY
        mock_boto3_clients["autoscaling"].create_auto_scaling_group.return_value = {}

        result = runner.invoke(cli, ["apply", "-f", sample_asg_yaml])
        assert result.exit_code == 0
        assert "Applying AutoScalingGroup/ecs-cluster-asg" in result.output
        mock_boto3_clients["autoscaling"].create_auto_scaling_group.assert_called_once()
        args = mock_boto3_clients["autoscaling"].create_auto_scaling_group.call_args[1]
        assert args["AutoScalingGroupName"] == "ecs-cluster-asg"
        assert args["MinSize"] == 2
        assert args["MaxSize"] == 10


    def test_apply_iam_role_creates(self, runner, sample_iam_role_yaml, mock_boto3_clients):
        """apply IAMRole → get_role (not found) → create_role + attach + put_policy."""
        no_such = type("NoSuchEntityException", (Exception,), {})
        mock_boto3_clients["iam"].exceptions = MagicMock()
        mock_boto3_clients["iam"].exceptions.NoSuchEntityException = no_such
        mock_boto3_clients["iam"].get_role.side_effect = no_such("not found")
        mock_boto3_clients["iam"].create_role.return_value = {"Role": {"RoleName": "ecsTaskRole"}}
        mock_boto3_clients["iam"].attach_role_policy.return_value = {}
        mock_boto3_clients["iam"].put_role_policy.return_value = {}

        result = runner.invoke(cli, ["apply", "-f", sample_iam_role_yaml])
        assert result.exit_code == 0
        assert "Applying IAMRole/ecsTaskRole" in result.output
        mock_boto3_clients["iam"].create_role.assert_called_once()
        create_args = mock_boto3_clients["iam"].create_role.call_args[1]
        assert create_args["RoleName"] == "ecsTaskRole"
        # AssumeRolePolicyDocument must be a JSON string for the AWS API
        assert isinstance(create_args["AssumeRolePolicyDocument"], str)
        doc = json.loads(create_args["AssumeRolePolicyDocument"])
        assert doc["Version"] == "2012-10-17"
        assert doc["Statement"][0]["Principal"]["Service"] == "ecs-tasks.amazonaws.com"
        # Managed policy attached
        mock_boto3_clients["iam"].attach_role_policy.assert_called_once_with(
            RoleName="ecsTaskRole",
            PolicyArn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        )
        # Inline policy put
        mock_boto3_clients["iam"].put_role_policy.assert_called_once()
        put_args = mock_boto3_clients["iam"].put_role_policy.call_args[1]
        assert put_args["RoleName"] == "ecsTaskRole"
        assert put_args["PolicyName"] == "S3Access"
        assert isinstance(put_args["PolicyDocument"], str)


    def test_apply_acm_certificate_new(self, runner, sample_acm_yaml, mock_boto3_clients):
        """apply Certificate → list_certificates (not found) → request_certificate."""
        mock_boto3_clients["acm"].list_certificates.return_value = LIST_CERTIFICATES_EMPTY
        mock_boto3_clients["acm"].request_certificate.return_value = REQUEST_CERTIFICATE_RESPONSE

        result = runner.invoke(cli, ["apply", "-f", sample_acm_yaml])
        assert result.exit_code == 0
        assert "Applying Certificate/api.example.com" in result.output
        mock_boto3_clients["acm"].request_certificate.assert_called_once()
        args = mock_boto3_clients["acm"].request_certificate.call_args[1]
        assert args["DomainName"] == "api.example.com"
        assert args["SubjectAlternativeNames"] == ["*.api.example.com"]
        assert args["ValidationMethod"] == "DNS"
        # Tags in Key/Value format per AWS CLI skeleton
        assert args["Tags"] == [{"Key": "Environment", "Value": "production"}]

    def test_apply_cloudmap_namespace_creates(self, runner, sample_cloudmap_yaml, mock_boto3_clients):
        """apply ServiceDiscoveryNamespace → list (empty) → create_private_dns_namespace."""
        mock_boto3_clients["servicediscovery"].list_namespaces.return_value = LIST_NAMESPACES_EMPTY
        mock_boto3_clients["servicediscovery"].create_private_dns_namespace.return_value = {"OperationId": "op-123"}

        result = runner.invoke(cli, ["apply", "-f", sample_cloudmap_yaml])
        assert result.exit_code == 0
        assert "Applying ServiceDiscoveryNamespace/internal.local" in result.output
        mock_boto3_clients["servicediscovery"].create_private_dns_namespace.assert_called_once()
        args = mock_boto3_clients["servicediscovery"].create_private_dns_namespace.call_args[1]
        assert args["Name"] == "internal.local"
        assert args["Vpc"] == "vpc-0123456789abcdef0"
        assert args["Description"] == "Internal namespace"


    def test_apply_service_requires_cluster(self, runner, sample_service_yaml, mock_boto3_clients, tmp_path):
        """apply Service without cluster (and no namespace in manifest) should error."""
        from pathlib import Path
        # Create a service YAML without namespace
        no_ns = tmp_path / "svc-no-ns.yaml"
        no_ns.write_text("""apiVersion: ecs/v1
kind: Service
metadata:
  name: orphan-svc
spec:
  taskDefinition: app
  desiredCount: 1
""")
        # Ensure no cluster from config either
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["apply", "-f", str(no_ns)])
            assert result.exit_code == 0
            assert "Cluster required" in result.output


# =============================================================================
# GET SUBCOMMAND - all resource types
# =============================================================================

class TestGetAllResourceTypes:
    """Validate `ecsctl get <type>` for every supported listing."""

    def test_get_cluster_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_clusters.return_value = LIST_CLUSTERS_RESPONSE
        mock_boto3_clients["ecs"].describe_clusters.return_value = DESCRIBE_CLUSTERS_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "cluster"])
        assert result.exit_code == 0
        assert "production" in result.output
        assert "ACTIVE" in result.output


    def test_get_service_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_services.return_value = LIST_SERVICES_RESPONSE
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "service", "--cluster", "production"])
        assert result.exit_code == 0
        assert "my-app-service" in result.output
        assert "ACTIVE" in result.output

    def test_get_service_requires_cluster(self, runner, mock_boto3_clients, tmp_path):
        from pathlib import Path
        with patch.object(Path, "home", return_value=tmp_path):
            with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
                result = runner.invoke(cli, ["get", "service"])
        assert result.exit_code == 0
        assert "Cluster required" in result.output

    def test_get_taskdefinition_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_task_definition_families.return_value = LIST_TASK_DEFINITION_FAMILIES_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "taskdefinition"])
        assert result.exit_code == 0
        assert "my-app" in result.output
        assert "worker" in result.output

    def test_get_task_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_tasks.return_value = LIST_TASKS_RESPONSE
        mock_boto3_clients["ecs"].describe_tasks.return_value = DESCRIBE_TASKS_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "task", "--cluster", "production"])
        assert result.exit_code == 0
        assert "abc123" in result.output
        assert "RUNNING" in result.output


    def test_get_loadbalancer_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["elbv2"].describe_load_balancers.return_value = DESCRIBE_LOAD_BALANCERS_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "loadbalancer"])
        assert result.exit_code == 0
        assert "api-alb" in result.output
        assert "application" in result.output
        assert "internet-facing" in result.output

    def test_get_autoscalinggroup_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["autoscaling"].describe_auto_scaling_groups.return_value = DESCRIBE_AUTO_SCALING_GROUPS_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "autoscalinggroup"])
        assert result.exit_code == 0
        assert "ecs-cluster-asg" in result.output

    def test_get_servicediscoverynamespace_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["servicediscovery"].list_namespaces.return_value = LIST_NAMESPACES_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "servicediscoverynamespace"])
        assert result.exit_code == 0
        assert "internal.local" in result.output
        assert "DNS_PRIVATE" in result.output

    def test_get_certificate_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["acm"].list_certificates.return_value = LIST_CERTIFICATES_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "certificate"])
        assert result.exit_code == 0
        assert "api.example.com" in result.output

    def test_get_iamrole_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["iam"].list_roles.return_value = LIST_ROLES_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "iamrole"])
        assert result.exit_code == 0
        assert "ecsTaskRole" in result.output


    def test_get_unknown_resource_type(self, runner, mock_boto3_clients):
        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "nonexistent"])
        assert result.exit_code == 0
        assert "unknown resource type" in result.output.lower()

    def test_get_service_empty_list(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_services.return_value = {"serviceArns": []}

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "service", "--cluster", "production"])
        assert result.exit_code == 0
        assert "No services found" in result.output

    def test_get_json_output(self, runner, mock_boto3_clients):
        with patch("ecsctl.cli.fetch_resource") as mock_fetch:
            from ecsctl.resources.base import ECSResource, Metadata
            mock_fetch.return_value = ECSResource(
                apiVersion="ecs/v1", kind="Service",
                metadata=Metadata(name="svc", namespace="prod"),
                spec={"desiredCount": 2},
            )
            result = runner.invoke(cli, ["get", "service", "svc", "-o", "json", "--cluster", "prod"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["kind"] == "Service"
        assert data["spec"]["desiredCount"] == 2


# =============================================================================
# DESCRIBE SUBCOMMAND
# =============================================================================

class TestDescribeCommand:
    """Validate `ecsctl describe <type> <name>`."""

    def test_describe_service_yaml(self, runner, mock_boto3_clients):
        with patch("ecsctl.cli.fetch_resource") as mock_fetch:
            from ecsctl.resources.base import ECSResource, Metadata
            mock_fetch.return_value = ECSResource(
                apiVersion="ecs/v1", kind="Service",
                metadata=Metadata(name="my-svc", namespace="production"),
                spec={"desiredCount": 3, "taskDefinition": "app:2"},
            )
            result = runner.invoke(cli, ["describe", "service", "my-svc", "-o", "yaml", "--cluster", "production"])
        assert result.exit_code == 0
        assert "desiredCount: 3" in result.output
        assert "taskDefinition: app:2" in result.output
        mock_fetch.assert_called_once()
        args = mock_fetch.call_args
        assert args[0] == ("service", "my-svc", "production") or args[0][:3] == ("service", "my-svc", "production")


    def test_describe_service_json(self, runner, mock_boto3_clients):
        with patch("ecsctl.cli.fetch_resource") as mock_fetch:
            from ecsctl.resources.base import ECSResource, Metadata
            mock_fetch.return_value = ECSResource(
                apiVersion="ecs/v1", kind="Service",
                metadata=Metadata(name="my-svc", namespace="production"),
                spec={"desiredCount": 3},
            )
            result = runner.invoke(cli, ["describe", "service", "my-svc", "-o", "json", "--cluster", "production"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["kind"] == "Service"
        assert data["metadata"]["name"] == "my-svc"

    def test_describe_table_output(self, runner, mock_boto3_clients):
        with patch("ecsctl.cli.fetch_resource") as mock_fetch:
            from ecsctl.resources.base import ECSResource, Metadata
            mock_fetch.return_value = ECSResource(
                apiVersion="ecs/v1", kind="Service",
                metadata=Metadata(name="svc"),
                spec={"desiredCount": 2, "taskDefinition": "app"},
            )
            result = runner.invoke(cli, ["describe", "service", "svc", "--cluster", "prod"])
        assert result.exit_code == 0
        assert "desiredCount" in result.output

    def test_describe_not_found(self, runner, mock_boto3_clients):
        with patch("ecsctl.cli.fetch_resource") as mock_fetch:
            mock_fetch.side_effect = ValueError("Service nonexistent not found")
            result = runner.invoke(cli, ["describe", "service", "nonexistent", "--cluster", "prod"])
        assert result.exit_code == 0
        assert "Error" in result.output
        assert "not found" in result.output


# =============================================================================
# DELETE SUBCOMMAND - all resource kinds
# =============================================================================

class TestDeleteAllKinds:
    """Validate `ecsctl delete -f <file>` for every supported kind."""

    def test_delete_service(self, runner, sample_service_yaml, mock_boto3_clients):
        mock_boto3_clients["ecs"].delete_service.return_value = {"service": {"status": "DRAINING"}}
        result = runner.invoke(cli, ["delete", "-f", sample_service_yaml, "--cluster", "production"])
        assert result.exit_code == 0
        assert "Deleting Service/my-app-service" in result.output
        mock_boto3_clients["ecs"].delete_service.assert_called_once_with(
            cluster="production", service="my-app-service", force=True,
        )


    def test_delete_task_definition(self, runner, sample_task_definition_yaml, mock_boto3_clients):
        mock_boto3_clients["ecs"].deregister_task_definition.return_value = {}
        result = runner.invoke(cli, ["delete", "-f", sample_task_definition_yaml])
        assert result.exit_code == 0
        assert "Deleting TaskDefinition/my-app" in result.output
        mock_boto3_clients["ecs"].deregister_task_definition.assert_called_once_with(
            taskDefinition="my-app",
        )

    def test_delete_loadbalancer(self, runner, sample_alb_yaml, mock_boto3_clients):
        mock_boto3_clients["elbv2"].describe_load_balancers.return_value = DESCRIBE_LOAD_BALANCERS_RESPONSE
        mock_boto3_clients["elbv2"].delete_load_balancer.return_value = {}
        result = runner.invoke(cli, ["delete", "-f", sample_alb_yaml])
        assert result.exit_code == 0
        assert "Deleting LoadBalancer/api-alb" in result.output
        mock_boto3_clients["elbv2"].delete_load_balancer.assert_called_once()
        args = mock_boto3_clients["elbv2"].delete_load_balancer.call_args[1]
        assert "LoadBalancerArn" in args

    def test_delete_asg(self, runner, sample_asg_yaml, mock_boto3_clients):
        mock_boto3_clients["autoscaling"].delete_auto_scaling_group.return_value = {}
        result = runner.invoke(cli, ["delete", "-f", sample_asg_yaml])
        assert result.exit_code == 0
        assert "Deleting AutoScalingGroup/ecs-cluster-asg" in result.output
        mock_boto3_clients["autoscaling"].delete_auto_scaling_group.assert_called_once_with(
            AutoScalingGroupName="ecs-cluster-asg", ForceDelete=True,
        )

    def test_delete_iam_role(self, runner, sample_iam_role_yaml, mock_boto3_clients):
        mock_boto3_clients["iam"].delete_role.return_value = {}
        result = runner.invoke(cli, ["delete", "-f", sample_iam_role_yaml])
        assert result.exit_code == 0
        assert "Deleting IAMRole/ecsTaskRole" in result.output
        mock_boto3_clients["iam"].delete_role.assert_called_once_with(RoleName="ecsTaskRole")


    def test_delete_certificate(self, runner, sample_acm_yaml, mock_boto3_clients):
        mock_boto3_clients["acm"].list_certificates.return_value = LIST_CERTIFICATES_RESPONSE
        mock_boto3_clients["acm"].delete_certificate.return_value = {}
        result = runner.invoke(cli, ["delete", "-f", sample_acm_yaml])
        assert result.exit_code == 0
        assert "Deleting Certificate/api.example.com" in result.output
        mock_boto3_clients["acm"].delete_certificate.assert_called_once()
        args = mock_boto3_clients["acm"].delete_certificate.call_args[1]
        assert args["CertificateArn"] == "arn:aws:acm:us-east-1:123456789012:certificate/abc-123"

    def test_delete_cloudmap_namespace(self, runner, sample_cloudmap_yaml, mock_boto3_clients):
        mock_boto3_clients["servicediscovery"].list_namespaces.return_value = LIST_NAMESPACES_RESPONSE
        mock_boto3_clients["servicediscovery"].delete_namespace.return_value = {}
        result = runner.invoke(cli, ["delete", "-f", sample_cloudmap_yaml])
        assert result.exit_code == 0
        assert "Deleting ServiceDiscoveryNamespace/internal.local" in result.output
        mock_boto3_clients["servicediscovery"].delete_namespace.assert_called_once_with(Id="ns-abc123")

    def test_delete_dry_run(self, runner, sample_service_yaml, mock_boto3_clients):
        result = runner.invoke(cli, ["delete", "-f", sample_service_yaml, "--dry-run", "--cluster", "production"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        assert "Dry Run Summary" in result.output
        mock_boto3_clients["ecs"].delete_service.assert_not_called()


# =============================================================================
# SCALE SUBCOMMAND
# =============================================================================

class TestScaleCommand:
    """Validate `ecsctl scale <service> <count>`."""

    def test_scale_executes(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].update_service.return_value = {
            "service": {"serviceName": "my-svc", "desiredCount": 5}
        }
        result = runner.invoke(cli, ["scale", "my-svc", "5", "--cluster", "production"])
        assert result.exit_code == 0
        mock_boto3_clients["ecs"].update_service.assert_called_once_with(
            cluster="production", service="my-svc", desiredCount=5,
        )

    def test_scale_dry_run(self, runner, mock_boto3_clients):
        result = runner.invoke(cli, ["scale", "my-svc", "10", "--dry-run", "--cluster", "production"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        mock_boto3_clients["ecs"].update_service.assert_not_called()


    def test_scale_invalid_count(self, runner, mock_boto3_clients):
        result = runner.invoke(cli, ["scale", "my-svc", "abc", "--cluster", "production"])
        assert result.exit_code != 0  # Click validates the int type


# =============================================================================
# RUN SUBCOMMAND
# =============================================================================

class TestRunCommand:
    """Validate `ecsctl run --image <img> --name <name>`."""

    def test_run_dry_run(self, runner, mock_boto3_clients):
        result = runner.invoke(cli, [
            "run", "--image", "nginx:latest", "--name", "one-off-task",
            "--cluster", "production", "--dry-run",
        ])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        mock_boto3_clients["ecs"].register_task_definition.assert_not_called()
        mock_boto3_clients["ecs"].run_task.assert_not_called()

    def test_run_executes(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].register_task_definition.return_value = {
            "taskDefinition": {
                "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/one-off-task:1"
            }
        }
        mock_boto3_clients["ecs"].run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123456789012:task/production/xyz"}]
        }
        result = runner.invoke(cli, [
            "run", "--image", "nginx:latest", "--name", "one-off-task",
            "--cluster", "production",
        ])
        assert result.exit_code == 0
        # Verify register_task_definition was called with correct params
        mock_boto3_clients["ecs"].register_task_definition.assert_called_once()
        reg_args = mock_boto3_clients["ecs"].register_task_definition.call_args[1]
        assert reg_args["family"] == "one-off-task"
        assert reg_args["containerDefinitions"][0]["name"] == "one-off-task"
        assert reg_args["containerDefinitions"][0]["image"] == "nginx:latest"
        assert reg_args["containerDefinitions"][0]["essential"] is True
        # Verify run_task was called
        mock_boto3_clients["ecs"].run_task.assert_called_once()
        run_args = mock_boto3_clients["ecs"].run_task.call_args[1]
        assert run_args["cluster"] == "production"
        assert run_args["launchType"] == "FARGATE"
        assert "task-definition/one-off-task:1" in run_args["taskDefinition"]



# =============================================================================
# EDIT SUBCOMMAND
# =============================================================================

class TestEditCommand:
    """Validate `ecsctl edit <type> <name>` flow."""

    def test_edit_no_changes(self, runner, mock_boto3_clients, tmp_path):
        """If editor makes no changes, prints 'No changes detected'."""
        from ecsctl.resources.base import ECSResource, Metadata
        import yaml

        resource = ECSResource(
            apiVersion="ecs/v1", kind="Service",
            metadata=Metadata(name="my-svc", namespace="production"),
            spec={"desiredCount": 2, "taskDefinition": "app:1"},
        )
        yaml_content = resource.to_yaml()

        with patch("ecsctl.editor.fetch_resource", return_value=resource):
            # Mock the editor to not change the file
            with patch("subprocess.call", side_effect=lambda args: None):
                result = runner.invoke(cli, [
                    "edit", "service", "my-svc", "--cluster", "production",
                    "--editor", "cat",
                ])
        assert result.exit_code == 0
        assert "No changes detected" in result.output

    def test_edit_with_changes_aborted(self, runner, mock_boto3_clients, tmp_path):
        """If user declines to apply, prints 'Aborted'."""
        from ecsctl.resources.base import ECSResource, Metadata
        import yaml

        resource = ECSResource(
            apiVersion="ecs/v1", kind="Service",
            metadata=Metadata(name="my-svc", namespace="production"),
            spec={"desiredCount": 2, "taskDefinition": "app:1"},
        )

        def mock_editor(args):
            # Modify the temp file to simulate user edit
            filepath = args[1]
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
            data["spec"]["desiredCount"] = 5
            with open(filepath, "w") as f:
                yaml.dump(data, f)

        with patch("ecsctl.editor.fetch_resource", return_value=resource):
            with patch("subprocess.call", side_effect=mock_editor):
                result = runner.invoke(cli, [
                    "edit", "service", "my-svc", "--cluster", "production",
                    "--editor", "vim",
                ], input="n\n")
        assert result.exit_code == 0
        assert "Changes to be applied" in result.output
        assert "Aborted" in result.output


    def test_edit_with_changes_applied_dry_run(self, runner, mock_boto3_clients):
        """If user confirms changes with --dry-run, logs but doesn't execute."""
        from ecsctl.resources.base import ECSResource, Metadata
        import yaml

        resource = ECSResource(
            apiVersion="ecs/v1", kind="Service",
            metadata=Metadata(name="my-svc", namespace="production"),
            spec={"desiredCount": 2, "taskDefinition": "app:1"},
        )

        def mock_editor(args):
            filepath = args[1]
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
            data["spec"]["desiredCount"] = 10
            with open(filepath, "w") as f:
                yaml.dump(data, f)

        with patch("ecsctl.editor.fetch_resource", return_value=resource):
            with patch("subprocess.call", side_effect=mock_editor):
                # Mock the applier too since edit calls apply_resource
                mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_RESPONSE
                result = runner.invoke(cli, [
                    "edit", "service", "my-svc", "--cluster", "production",
                    "--editor", "vim", "--dry-run",
                ], input="y\n")
        assert result.exit_code == 0
        assert "Changes to be applied" in result.output
        assert "DRY-RUN" in result.output


# =============================================================================
# CONFIG SUBCOMMANDS
# =============================================================================

class TestConfigSubcommands:
    """Validate all config subcommands."""

    def test_config_set_full(self, runner, tmp_path):
        from pathlib import Path
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, [
                "config", "set", "production",
                "--cluster-name", "prod-cluster",
                "--aws-profile", "prod-profile",
                "--aws-region", "us-east-1",
            ])
        assert result.exit_code == 0
        assert "saved" in result.output
        # Verify file contents
        config = json.loads((tmp_path / ".ecsctl" / "config.json").read_text())
        assert config["contexts"]["production"]["cluster_name"] == "prod-cluster"
        assert config["contexts"]["production"]["aws_profile"] == "prod-profile"
        assert config["contexts"]["production"]["aws_region"] == "us-east-1"

    def test_config_context_switch(self, runner, tmp_path):
        from pathlib import Path
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({
            "current": "dev",
            "contexts": {"dev": {"cluster_name": "dev"}, "prod": {"cluster_name": "production"}},
        }))
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["config", "context", "prod"])
        assert result.exit_code == 0
        assert "Switched to context 'prod'" in result.output
        # Verify persistence
        config = json.loads((config_dir / "config.json").read_text())
        assert config["current"] == "prod"


    def test_config_context_nonexistent(self, runner, tmp_path):
        from pathlib import Path
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({
            "current": "dev", "contexts": {"dev": {}},
        }))
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["config", "context", "nonexistent"])
        assert result.exit_code != 0

    def test_config_show_current(self, runner, tmp_path):
        from pathlib import Path
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({
            "current": "prod",
            "contexts": {"prod": {"cluster_name": "production", "aws_region": "us-east-1"}},
        }))
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "production" in result.output or "cluster_name" in result.output

    def test_config_show_all(self, runner, tmp_path):
        from pathlib import Path
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({
            "current": "prod",
            "contexts": {
                "prod": {"cluster_name": "production"},
                "staging": {"cluster_name": "staging"},
            },
        }))
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["config", "show", "--show-all"])
        assert result.exit_code == 0
        assert "prod" in result.output
        assert "staging" in result.output
