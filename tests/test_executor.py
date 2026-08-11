"""Tests for ecsctl/executor.py - AWSExecutor with dry-run support."""

import pytest
from unittest.mock import patch, MagicMock
from ecsctl.executor import AWSExecutor


class TestAWSExecutor:
    def test_init_creates_clients(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        assert "ecs" in executor.clients
        assert "elbv2" in executor.clients
        assert "autoscaling" in executor.clients
        assert "iam" in executor.clients
        assert "acm" in executor.clients
        assert "servicediscovery" in executor.clients

    def test_init_dry_run_flag(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=True)
        assert executor.dry_run is True
        executor2 = AWSExecutor(dry_run=False)
        assert executor2.dry_run is False

    def test_call_executes_when_not_dry_run(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["ecs"].describe_clusters.return_value = {"clusters": []}

        result = executor.call("ecs", "describe_clusters", {"clusters": ["test"]})

        mock_boto3_clients["ecs"].describe_clusters.assert_called_once_with(clusters=["test"])
        assert result == {"clusters": []}

    def test_call_logs_when_dry_run(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=True)
        result = executor.call("ecs", "create_service", {
            "cluster": "prod",
            "serviceName": "my-svc",
        })

        assert result["DryRun"] is True
        assert result["action"] == "create_service"
        assert result["service"] == "ecs"
        assert len(executor.logs) == 1
        assert executor.logs[0]["service"] == "ecs"
        assert executor.logs[0]["action"] == "create_service"
        assert executor.logs[0]["params"]["cluster"] == "prod"

        # Should NOT have called the real client
        mock_boto3_clients["ecs"].create_service.assert_not_called()

    def test_call_multiple_dry_run_logs(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=True)
        executor.call("ecs", "register_task_definition", {"family": "app"})
        executor.call("ecs", "create_service", {"serviceName": "svc"})
        executor.call("iam", "create_role", {"RoleName": "role"})

        assert len(executor.logs) == 3
        assert executor.logs[0]["action"] == "register_task_definition"
        assert executor.logs[1]["action"] == "create_service"
        assert executor.logs[2]["service"] == "iam"

    def test_flush_logs_outputs(self, mock_boto3_clients, capsys):
        executor = AWSExecutor(dry_run=True)
        executor.call("ecs", "create_service", {"serviceName": "svc", "cluster": "prod"})
        executor.flush_logs()

        captured = capsys.readouterr()
        assert "Dry Run Summary" in captured.out
        assert "create_service" in captured.out
        assert "serviceName" in captured.out

    def test_flush_logs_no_output_when_empty(self, mock_boto3_clients, capsys):
        executor = AWSExecutor(dry_run=True)
        executor.flush_logs()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_call_passes_correct_params_to_boto3(self, mock_boto3_clients):
        executor = AWSExecutor(dry_run=False)
        mock_boto3_clients["elbv2"].create_load_balancer.return_value = {"LoadBalancers": []}

        params = {
            "Name": "my-alb",
            "Subnets": ["subnet-123"],
            "SecurityGroups": ["sg-123"],
            "Scheme": "internet-facing",
            "Type": "application",
        }
        executor.call("elbv2", "create_load_balancer", params)

        mock_boto3_clients["elbv2"].create_load_balancer.assert_called_once_with(**params)
