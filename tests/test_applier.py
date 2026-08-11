"""Tests for ecsctl/applier.py - All apply handlers against AWS CLI skeleton shapes."""

import json
import pytest
from unittest.mock import patch, MagicMock
from ecsctl.resources.base import ECSResource, Metadata
from ecsctl.applier import (
    apply_resource, apply_task_definition, apply_service,
    apply_cluster, apply_asg, apply_alb, apply_sd_namespace,
    apply_sd_service, apply_certificate, apply_iam_role,
    _convert_tags,
)
from ecsctl.executor import AWSExecutor
from tests.fixtures.aws_responses import *


class TestConvertTags:
    def test_dict_tags(self):
        result = _convert_tags({"Env": "prod", "Team": "platform"})
        assert result == [
            {"Key": "Env", "Value": "prod"},
            {"Key": "Team", "Value": "platform"},
        ]

    def test_list_tags_already_correct(self):
        tags = [{"Key": "Env", "Value": "prod"}]
        assert _convert_tags(tags) == tags

    def test_empty_tags(self):
        assert _convert_tags(None) == []
        assert _convert_tags([]) == []
        assert _convert_tags({}) == []

    def test_list_tags_unknown_format(self):
        # Tags as a list of something that doesn't have "Key"
        tags = [{"name": "Env", "value": "prod"}]
        assert _convert_tags(tags) == []


class TestApplyTaskDefinition:
    def test_registers_task_definition(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].register_task_definition.return_value = REGISTER_TASK_DEFINITION_RESPONSE

        spec = {
            "family": "my-app",
            "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            "memory": "512",
            "containerDefinitions": [
                {"name": "app", "image": "nginx:latest", "essential": True}
            ],
        }
        result = apply_task_definition(spec, executor)

        mock_boto3_clients["ecs"].register_task_definition.assert_called_once_with(**spec)
        assert "taskDefinition" in result

    def test_dry_run_does_not_call_aws(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=True)
        spec = {"family": "my-app", "containerDefinitions": []}
        result = apply_task_definition(spec, executor)

        assert result["DryRun"] is True
        mock_boto3_clients["ecs"].register_task_definition.assert_not_called()


class TestApplyService:
    def test_creates_service_when_not_found(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        # describe_services returns empty (service doesn't exist)
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_EMPTY
        mock_boto3_clients["ecs"].create_service.return_value = {"service": {"serviceName": "my-svc"}}

        spec = {
            "taskDefinition": "my-app",
            "desiredCount": 2,
            "launchType": "FARGATE",
        }
        result = apply_service("my-svc", spec, executor, "production")

        mock_boto3_clients["ecs"].create_service.assert_called_once()
        call_args = mock_boto3_clients["ecs"].create_service.call_args[1]
        assert call_args["cluster"] == "production"
        assert call_args["serviceName"] == "my-svc"
        assert call_args["taskDefinition"] == "my-app"

    def test_updates_service_when_active(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_RESPONSE
        mock_boto3_clients["ecs"].update_service.return_value = {"service": {"serviceName": "my-app-service"}}

        spec = {
            "taskDefinition": "my-app:2",
            "desiredCount": 3,
            "forceNewDeployment": True,
        }
        result = apply_service("my-app-service", spec, executor, "production")

        mock_boto3_clients["ecs"].update_service.assert_called_once()
        call_args = mock_boto3_clients["ecs"].update_service.call_args[1]
        assert call_args["cluster"] == "production"
        assert call_args["service"] == "my-app-service"
        assert call_args["taskDefinition"] == "my-app:2"
        assert call_args["desiredCount"] == 3

    def test_creates_when_inactive(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_INACTIVE
        mock_boto3_clients["ecs"].create_service.return_value = {"service": {}}

        spec = {"taskDefinition": "my-app", "desiredCount": 1}
        apply_service("my-app-service", spec, executor, "production")

        mock_boto3_clients["ecs"].create_service.assert_called_once()

    def test_update_only_passes_allowed_fields(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_RESPONSE
        mock_boto3_clients["ecs"].update_service.return_value = {"service": {}}

        spec = {
            "taskDefinition": "my-app:2",
            "desiredCount": 5,
            "launchType": "FARGATE",  # NOT in allowed list for update
            "networkConfiguration": {"awsvpcConfiguration": {"subnets": ["subnet-123"]}},
        }
        apply_service("my-app-service", spec, executor, "production")

        call_args = mock_boto3_clients["ecs"].update_service.call_args[1]
        assert "taskDefinition" in call_args
        assert "desiredCount" in call_args
        assert "networkConfiguration" in call_args
        # launchType is NOT in the allowed list for update_service
        assert "launchType" not in call_args


class TestApplyCluster:
    def test_creates_cluster_when_not_found(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].describe_clusters.side_effect = Exception("Cluster not found")
        mock_boto3_clients["ecs"].create_cluster.return_value = {"cluster": {"clusterName": "test"}}

        result = apply_cluster("test", {}, executor)
        mock_boto3_clients["ecs"].create_cluster.assert_called_once()

    def test_updates_settings_when_exists(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].describe_clusters.return_value = DESCRIBE_CLUSTERS_RESPONSE
        mock_boto3_clients["ecs"].put_cluster_settings.return_value = {}

        spec = {"settings": [{"name": "containerInsights", "value": "enabled"}]}
        apply_cluster("production", spec, executor)

        mock_boto3_clients["ecs"].put_cluster_settings.assert_called_once()


class TestApplyASG:
    def test_creates_asg_when_not_found(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["autoscaling"].describe_auto_scaling_groups.return_value = DESCRIBE_AUTO_SCALING_GROUPS_EMPTY
        mock_boto3_clients["autoscaling"].create_auto_scaling_group.return_value = {}

        spec = {"MinSize": 2, "MaxSize": 10, "DesiredCapacity": 3}
        apply_asg("my-asg", spec, executor)

        mock_boto3_clients["autoscaling"].create_auto_scaling_group.assert_called_once()
        call_args = mock_boto3_clients["autoscaling"].create_auto_scaling_group.call_args[1]
        assert call_args["AutoScalingGroupName"] == "my-asg"
        assert call_args["MinSize"] == 2

    def test_updates_asg_when_exists(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["autoscaling"].describe_auto_scaling_groups.return_value = DESCRIBE_AUTO_SCALING_GROUPS_RESPONSE
        mock_boto3_clients["autoscaling"].update_auto_scaling_group.return_value = {}

        spec = {"MinSize": 3, "MaxSize": 15, "DesiredCapacity": 5}
        apply_asg("ecs-cluster-asg", spec, executor)

        mock_boto3_clients["autoscaling"].update_auto_scaling_group.assert_called_once()


class TestApplyALB:
    def test_creates_alb_when_not_found(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["elbv2"].describe_load_balancers.side_effect = Exception("Not found")
        mock_boto3_clients["elbv2"].create_load_balancer.return_value = {"LoadBalancers": []}

        spec = {
            "subnets": ["subnet-123", "subnet-456"],
            "securityGroups": ["sg-123"],
            "scheme": "internet-facing",
            "type": "application",
            "tags": {"Env": "prod"},
        }
        apply_alb("api-alb", spec, executor)

        mock_boto3_clients["elbv2"].create_load_balancer.assert_called_once()
        call_args = mock_boto3_clients["elbv2"].create_load_balancer.call_args[1]
        # Verify AWS API shape: Name, Subnets, SecurityGroups, Scheme, Type, Tags
        assert call_args["Name"] == "api-alb"
        assert call_args["Subnets"] == ["subnet-123", "subnet-456"]
        assert call_args["SecurityGroups"] == ["sg-123"]
        assert call_args["Scheme"] == "internet-facing"
        assert call_args["Type"] == "application"
        # Tags should be converted to Key/Value format
        assert call_args["Tags"] == [{"Key": "Env", "Value": "prod"}]

    def test_skips_when_exists(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["elbv2"].describe_load_balancers.return_value = DESCRIBE_LOAD_BALANCERS_RESPONSE

        spec = {"subnets": ["subnet-123"]}
        result = apply_alb("api-alb", spec, executor)

        assert "exists" in result["message"]
        mock_boto3_clients["elbv2"].create_load_balancer.assert_not_called()


class TestApplySDNamespace:
    def test_creates_private_namespace(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["servicediscovery"].list_namespaces.return_value = LIST_NAMESPACES_EMPTY
        mock_boto3_clients["servicediscovery"].create_private_dns_namespace.return_value = {"OperationId": "op-123"}

        spec = {"type": "DNS_PRIVATE", "description": "Internal", "vpcId": "vpc-123"}
        apply_sd_namespace("internal.local", spec, executor)

        mock_boto3_clients["servicediscovery"].create_private_dns_namespace.assert_called_once()
        call_args = mock_boto3_clients["servicediscovery"].create_private_dns_namespace.call_args[1]
        assert call_args["Name"] == "internal.local"
        assert call_args["Vpc"] == "vpc-123"

    def test_creates_public_namespace(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["servicediscovery"].list_namespaces.return_value = LIST_NAMESPACES_EMPTY
        mock_boto3_clients["servicediscovery"].create_public_dns_namespace.return_value = {"OperationId": "op-456"}

        spec = {"type": "DNS_PUBLIC", "description": "Public"}
        apply_sd_namespace("public.example.com", spec, executor)

        mock_boto3_clients["servicediscovery"].create_public_dns_namespace.assert_called_once()

    def test_skips_when_exists(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["servicediscovery"].list_namespaces.return_value = LIST_NAMESPACES_RESPONSE

        spec = {"type": "DNS_PRIVATE", "vpcId": "vpc-123"}
        result = apply_sd_namespace("internal.local", spec, executor)

        assert "already exists" in result["message"]


class TestApplySDService:
    def test_creates_service_when_not_found(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["servicediscovery"].list_services.return_value = LIST_SERVICES_SD_EMPTY
        mock_boto3_clients["servicediscovery"].create_service.return_value = {"Service": {"Id": "srv-new"}}

        spec = {"namespaceId": "ns-123", "dnsConfig": {"type": "A", "ttl": 60}}
        apply_sd_service("api-service", spec, executor)

        mock_boto3_clients["servicediscovery"].create_service.assert_called_once()

    def test_updates_when_found(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["servicediscovery"].list_services.return_value = LIST_SERVICES_SD_RESPONSE
        mock_boto3_clients["servicediscovery"].update_service.return_value = {"OperationId": "op-789"}

        spec = {"dnsConfig": {"type": "A", "ttl": 120}}
        apply_sd_service("api-service", spec, executor)

        mock_boto3_clients["servicediscovery"].update_service.assert_called_once()
        call_args = mock_boto3_clients["servicediscovery"].update_service.call_args[1]
        assert call_args["Id"] == "srv-abc123"


class TestApplyCertificate:
    def test_skips_when_domain_exists(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["acm"].list_certificates.return_value = LIST_CERTIFICATES_RESPONSE

        spec = {"domainName": "api.example.com", "validationMethod": "DNS"}
        result = apply_certificate("api.example.com", spec, executor)

        assert "already exists" in result["message"]
        assert "arn" in result

    def test_requests_new_certificate(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["acm"].list_certificates.return_value = LIST_CERTIFICATES_EMPTY
        mock_boto3_clients["acm"].request_certificate.return_value = REQUEST_CERTIFICATE_RESPONSE

        spec = {
            "domainName": "new.example.com",
            "subjectAlternativeNames": ["*.new.example.com"],
            "validationMethod": "DNS",
            "tags": [{"Key": "Env", "Value": "prod"}],
        }
        apply_certificate("new.example.com", spec, executor)

        mock_boto3_clients["acm"].request_certificate.assert_called_once()
        call_args = mock_boto3_clients["acm"].request_certificate.call_args[1]
        # Verify matches AWS CLI skeleton shape
        assert call_args["DomainName"] == "new.example.com"
        assert call_args["SubjectAlternativeNames"] == ["*.new.example.com"]
        assert call_args["ValidationMethod"] == "DNS"
        assert call_args["Tags"] == [{"Key": "Env", "Value": "prod"}]


class TestApplyIAMRole:
    def test_creates_new_role(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        # Simulate role not found
        mock_boto3_clients["iam"].get_role.side_effect = (
            mock_boto3_clients["iam"].exceptions.NoSuchEntityException
        ) = type("NoSuchEntityException", (Exception,), {})()
        # Re-setup: need proper exception class
        no_such = type("NoSuchEntityException", (Exception,), {})
        mock_boto3_clients["iam"].exceptions = MagicMock()
        mock_boto3_clients["iam"].exceptions.NoSuchEntityException = no_such
        mock_boto3_clients["iam"].get_role.side_effect = no_such("Role not found")
        mock_boto3_clients["iam"].create_role.return_value = {"Role": {"RoleName": "ecsTaskRole"}}
        mock_boto3_clients["iam"].attach_role_policy.return_value = {}
        mock_boto3_clients["iam"].put_role_policy.return_value = {}

        spec = {
            "assumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Principal": {"Service": "ecs-tasks.amazonaws.com"}, "Action": "sts:AssumeRole"}],
            },
            "managedPolicyArns": ["arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"],
            "inlinePolicies": [
                {
                    "PolicyName": "S3Access",
                    "PolicyDocument": {"Version": "2012-10-17", "Statement": []},
                }
            ],
            "tags": [{"Key": "Purpose", "Value": "ECS"}],
        }
        result = apply_iam_role("ecsTaskRole", spec, executor)

        mock_boto3_clients["iam"].create_role.assert_called_once()
        create_args = mock_boto3_clients["iam"].create_role.call_args[1]
        # AWS CLI skeleton: RoleName, AssumeRolePolicyDocument (string), Tags
        assert create_args["RoleName"] == "ecsTaskRole"
        assert isinstance(create_args["AssumeRolePolicyDocument"], str)
        # Verify it's valid JSON
        json.loads(create_args["AssumeRolePolicyDocument"])

        mock_boto3_clients["iam"].attach_role_policy.assert_called_once()
        mock_boto3_clients["iam"].put_role_policy.assert_called_once()
        assert "created" in result["message"]

    def test_updates_existing_role(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["iam"].get_role.return_value = GET_ROLE_RESPONSE
        mock_boto3_clients["iam"].list_attached_role_policies.return_value = LIST_ATTACHED_ROLE_POLICIES_RESPONSE
        mock_boto3_clients["iam"].list_role_policies.return_value = {"PolicyNames": ["OldPolicy"]}
        mock_boto3_clients["iam"].update_assume_role_policy.return_value = {}
        mock_boto3_clients["iam"].attach_role_policy.return_value = {}
        mock_boto3_clients["iam"].detach_role_policy.return_value = {}
        mock_boto3_clients["iam"].delete_role_policy.return_value = {}
        mock_boto3_clients["iam"].put_role_policy.return_value = {}

        spec = {
            "assumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": []},
            "managedPolicyArns": [
                "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
                "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",  # new
            ],
            "inlinePolicies": [
                {"PolicyName": "NewPolicy", "PolicyDocument": {"Version": "2012-10-17", "Statement": []}},
            ],
        }
        result = apply_iam_role("ecsTaskRole", spec, executor)

        # Should update assume role policy (it's a dict → serialized to string)
        mock_boto3_clients["iam"].update_assume_role_policy.assert_called_once()
        update_args = mock_boto3_clients["iam"].update_assume_role_policy.call_args[1]
        assert isinstance(update_args["PolicyDocument"], str)

        # Should attach new policy (S3ReadOnly not in current)
        mock_boto3_clients["iam"].attach_role_policy.assert_called_once()

        # Should delete old inline policy (OldPolicy not in desired)
        mock_boto3_clients["iam"].delete_role_policy.assert_called_once()

        # Should put new inline policy
        mock_boto3_clients["iam"].put_role_policy.assert_called_once()

        assert "updated" in result["message"]


class TestApplyResourceDispatch:
    def test_dispatches_task_definition(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=True)
        resource = ECSResource(
            apiVersion="ecs/v1",
            kind="TaskDefinition",
            metadata=Metadata(name="my-app"),
            spec={"family": "my-app", "containerDefinitions": []},
        )
        result = apply_resource(resource, executor, "production")
        assert result["DryRun"] is True

    def test_dispatches_service(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=True)
        resource = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="my-svc"),
            spec={"taskDefinition": "app", "desiredCount": 1},
        )
        result = apply_resource(resource, executor, "production")
        assert result["DryRun"] is True

    def test_unknown_kind_raises(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        resource = ECSResource(
            apiVersion="ecs/v1",
            kind="UnknownKind",
            metadata=Metadata(name="x"),
            spec={},
        )
        with pytest.raises(ValueError, match="Unknown resource kind"):
            apply_resource(resource, executor)

    def test_kind_normalization(self, mock_boto3_clients):
        """Verify that kind normalization (lowercase, strip dashes/underscores) works."""
        executor = AWSExecutor(dry_run=True)
        # Test with dashes and mixed case
        resource = ECSResource(
            apiVersion="ecs/v1",
            kind="Task-Definition",
            metadata=Metadata(name="app"),
            spec={"family": "app", "containerDefinitions": []},
        )
        result = apply_resource(resource, executor, "prod")
        assert result["DryRun"] is True
