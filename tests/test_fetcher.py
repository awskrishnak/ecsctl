"""Tests for ecsctl/fetcher.py - Resource fetching and readonly field stripping."""

import pytest
from unittest.mock import patch, MagicMock
from ecsctl.fetcher import (
    fetch_resource, fetch_task_definition, fetch_service,
    fetch_cluster, fetch_alb, fetch_asg, fetch_sd_namespace,
    fetch_sd_service, fetch_certificate, fetch_iam_role,
    strip_readonly, READONLY_STRIPPERS,
)
from tests.fixtures.aws_responses import *


class TestStripReadonly:
    def test_strips_task_definition_fields(self):
        data = {
            "taskDefinitionArn": "arn:aws:ecs:...",
            "family": "my-app",
            "revision": 3,
            "status": "ACTIVE",
            "requiresAttributes": [],
            "compatibilities": ["FARGATE"],
            "registeredAt": "2025-01-01T00:00:00Z",
            "registeredBy": "arn:aws:iam::...",
            "cpu": "256",
            "memory": "512",
            "containerDefinitions": [],
        }
        result = strip_readonly("TaskDefinition", data)
        assert "taskDefinitionArn" not in result
        assert "revision" not in result
        assert "status" not in result
        assert "requiresAttributes" not in result
        assert "compatibilities" not in result
        assert "registeredAt" not in result
        assert "registeredBy" not in result
        # These should remain
        assert result["family"] == "my-app"
        assert result["cpu"] == "256"
        assert result["memory"] == "512"
        assert result["containerDefinitions"] == []

    def test_strips_service_fields(self):
        data = {
            "serviceArn": "arn:...",
            "clusterArn": "arn:...",
            "serviceName": "my-svc",
            "createdAt": "2025-01-01",
            "createdBy": "arn:...",
            "deployments": [],
            "events": [],
            "runningCount": 2,
            "pendingCount": 0,
            "status": "ACTIVE",
            "taskDefinition": "my-app:1",
            "desiredCount": 2,
        }
        result = strip_readonly("Service", data)
        assert "serviceArn" not in result
        assert "clusterArn" not in result
        assert "createdAt" not in result
        assert "deployments" not in result
        assert "events" not in result
        assert "runningCount" not in result
        assert "status" not in result
        # Mutable fields remain
        assert result["serviceName"] == "my-svc"
        assert result["taskDefinition"] == "my-app:1"
        assert result["desiredCount"] == 2

    def test_strips_alb_fields(self):
        data = {
            "LoadBalancerArn": "arn:...",
            "LoadBalancerName": "api-alb",
            "DNSName": "api-alb-123.elb.amazonaws.com",
            "CanonicalHostedZoneId": "Z123",
            "CreatedTime": "2025-01-01",
            "State": {"Code": "active"},
            "VpcId": "vpc-123",
            "Type": "application",
            "Scheme": "internet-facing",
        }
        result = strip_readonly("LoadBalancer", data)
        assert "LoadBalancerArn" not in result
        assert "DNSName" not in result
        assert "CanonicalHostedZoneId" not in result
        assert "CreatedTime" not in result
        assert "State" not in result
        assert "VpcId" not in result
        # Remain
        assert result["LoadBalancerName"] == "api-alb"
        assert result["Type"] == "application"
        assert result["Scheme"] == "internet-facing"

    def test_strips_iam_role_fields(self):
        data = {
            "RoleName": "ecsTaskRole",
            "Arn": "arn:aws:iam::123456789012:role/ecsTaskRole",
            "RoleId": "AROA123",
            "CreateDate": "2025-01-01",
            "RoleLastUsed": {},
            "MaxSessionDuration": 3600,
            "AssumeRolePolicyDocument": "{}",
        }
        result = strip_readonly("IAMRole", data)
        assert "Arn" not in result
        assert "RoleId" not in result
        assert "CreateDate" not in result
        assert "RoleLastUsed" not in result
        assert "MaxSessionDuration" not in result
        assert result["RoleName"] == "ecsTaskRole"
        assert result["AssumeRolePolicyDocument"] == "{}"

    def test_unknown_kind_returns_all(self):
        data = {"key1": "val1", "key2": "val2"}
        result = strip_readonly("UnknownKind", data)
        assert result == data

    def test_all_strippers_have_valid_keys(self):
        """Verify READONLY_STRIPPERS has entries for all expected resource kinds."""
        expected_kinds = [
            "TaskDefinition", "Service", "Cluster", "LoadBalancer",
            "AutoScalingGroup", "ServiceDiscoveryNamespace",
            "ServiceDiscoveryService", "Certificate", "IAMRole",
        ]
        for kind in expected_kinds:
            assert kind in READONLY_STRIPPERS, f"Missing READONLY_STRIPPERS for {kind}"
            assert isinstance(READONLY_STRIPPERS[kind], list)
            assert len(READONLY_STRIPPERS[kind]) > 0


class TestFetchTaskDefinition:
    def test_fetch_returns_raw_data(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_task_definition.return_value = DESCRIBE_TASK_DEFINITION_RESPONSE

            result = fetch_task_definition("my-app:1")
            mock_ecs.describe_task_definition.assert_called_once_with(taskDefinition="my-app:1")
            assert result["family"] == "my-app"


class TestFetchService:
    def test_fetch_returns_service_data(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_services.return_value = DESCRIBE_SERVICES_RESPONSE

            result = fetch_service("production", "my-app-service")
            mock_ecs.describe_services.assert_called_once_with(
                cluster="production", services=["my-app-service"]
            )
            assert result["serviceName"] == "my-app-service"

    def test_fetch_raises_when_not_found(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_services.return_value = DESCRIBE_SERVICES_EMPTY

            with pytest.raises(ValueError, match="not found"):
                fetch_service("production", "nonexistent")


class TestFetchCluster:
    def test_fetch_returns_cluster_data(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_clusters.return_value = DESCRIBE_CLUSTERS_RESPONSE

            result = fetch_cluster("production")
            assert result["clusterName"] == "production"

    def test_fetch_raises_when_not_found(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_clusters.return_value = {"clusters": [], "failures": []}

            with pytest.raises(ValueError, match="not found"):
                fetch_cluster("nonexistent")


class TestFetchALB:
    def test_fetch_returns_alb_with_listeners(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_elbv2 = MagicMock()
            mock_client.return_value = mock_elbv2
            mock_elbv2.describe_load_balancers.return_value = DESCRIBE_LOAD_BALANCERS_RESPONSE
            mock_elbv2.describe_listeners.return_value = DESCRIBE_LISTENERS_RESPONSE

            result = fetch_alb("api-alb")
            assert result["LoadBalancerName"] == "api-alb"
            assert "Listeners" in result
            assert len(result["Listeners"]) == 1

    def test_fetch_raises_when_not_found(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_elbv2 = MagicMock()
            mock_client.return_value = mock_elbv2
            mock_elbv2.describe_load_balancers.return_value = DESCRIBE_LOAD_BALANCERS_EMPTY

            with pytest.raises(ValueError, match="not found"):
                fetch_alb("nonexistent")


class TestFetchASG:
    def test_fetch_returns_asg_data(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_asg = MagicMock()
            mock_client.return_value = mock_asg
            mock_asg.describe_auto_scaling_groups.return_value = DESCRIBE_AUTO_SCALING_GROUPS_RESPONSE

            result = fetch_asg("ecs-cluster-asg")
            assert result["AutoScalingGroupName"] == "ecs-cluster-asg"
            assert result["MinSize"] == 2

    def test_fetch_raises_when_not_found(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_asg = MagicMock()
            mock_client.return_value = mock_asg
            mock_asg.describe_auto_scaling_groups.return_value = DESCRIBE_AUTO_SCALING_GROUPS_EMPTY

            with pytest.raises(ValueError, match="not found"):
                fetch_asg("nonexistent")


class TestFetchSDNamespace:
    def test_fetch_returns_namespace(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_sd = MagicMock()
            mock_client.return_value = mock_sd
            mock_sd.list_namespaces.return_value = LIST_NAMESPACES_RESPONSE

            result = fetch_sd_namespace("internal.local")
            assert result["Name"] == "internal.local"
            assert result["Id"] == "ns-abc123"

    def test_fetch_raises_when_not_found(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_sd = MagicMock()
            mock_client.return_value = mock_sd
            mock_sd.list_namespaces.return_value = LIST_NAMESPACES_EMPTY

            with pytest.raises(ValueError, match="not found"):
                fetch_sd_namespace("nonexistent")


class TestFetchCertificate:
    def test_fetch_by_domain_name(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_acm = MagicMock()
            mock_client.return_value = mock_acm
            mock_acm.list_certificates.return_value = LIST_CERTIFICATES_RESPONSE
            mock_acm.describe_certificate.return_value = DESCRIBE_CERTIFICATE_RESPONSE

            result = fetch_certificate("api.example.com")
            assert result["DomainName"] == "api.example.com"

    def test_fetch_by_arn(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_acm = MagicMock()
            mock_client.return_value = mock_acm
            mock_acm.describe_certificate.return_value = DESCRIBE_CERTIFICATE_RESPONSE

            result = fetch_certificate("arn:aws:acm:us-east-1:123456789012:certificate/abc-123")
            mock_acm.describe_certificate.assert_called_once_with(
                CertificateArn="arn:aws:acm:us-east-1:123456789012:certificate/abc-123"
            )
            assert result["DomainName"] == "api.example.com"

    def test_fetch_raises_when_not_found(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_acm = MagicMock()
            mock_client.return_value = mock_acm
            mock_acm.list_certificates.return_value = LIST_CERTIFICATES_EMPTY

            with pytest.raises(ValueError, match="not found"):
                fetch_certificate("nonexistent.example.com")


class TestFetchIAMRole:
    def test_fetch_returns_enriched_role(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_iam = MagicMock()
            mock_client.return_value = mock_iam
            mock_iam.get_role.return_value = GET_ROLE_RESPONSE
            mock_iam.list_attached_role_policies.return_value = LIST_ATTACHED_ROLE_POLICIES_RESPONSE
            mock_iam.list_role_policies.return_value = LIST_ROLE_POLICIES_RESPONSE
            mock_iam.get_role_policy.return_value = GET_ROLE_POLICY_RESPONSE

            result = fetch_iam_role("ecsTaskRole")
            assert result["RoleName"] == "ecsTaskRole"
            assert "AttachedPolicies" in result
            assert len(result["AttachedPolicies"]) == 1
            assert "InlinePolicies" in result
            assert len(result["InlinePolicies"]) == 1
            assert result["InlinePolicies"][0]["PolicyName"] == "S3Access"


class TestFetchResourceDispatch:
    def test_dispatches_service_with_cluster(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_services.return_value = DESCRIBE_SERVICES_RESPONSE

            resource = fetch_resource("service", "my-app-service", "production")
            assert resource.kind == "service"
            assert resource.metadata.name == "my-app-service"
            assert resource.metadata.namespace == "production"
            # Readonly fields should be stripped
            assert "serviceArn" not in resource.spec
            assert "clusterArn" not in resource.spec

    def test_dispatches_taskdefinition(self):
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_task_definition.return_value = DESCRIBE_TASK_DEFINITION_RESPONSE

            resource = fetch_resource("taskdefinition", "my-app:1")
            assert resource.kind == "taskdefinition"

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown resource kind"):
            fetch_resource("unknown", "name")

    def test_kind_normalization(self):
        """Test that dashes, underscores, and case are normalized."""
        with patch("boto3.Session") as mock_session_cls:
            mock_client = mock_session_cls.return_value.client
            mock_ecs = MagicMock()
            mock_client.return_value = mock_ecs
            mock_ecs.describe_task_definition.return_value = DESCRIBE_TASK_DEFINITION_RESPONSE

            resource = fetch_resource("Task-Definition", "my-app:1")
            assert resource.kind == "Task-Definition"
