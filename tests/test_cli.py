"""Tests for ecsctl/cli.py - Click CLI integration tests."""

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from ecsctl.cli import cli
from tests.fixtures.aws_responses import *


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path):
    """Mock ConfigManager to use a temp config."""
    from pathlib import Path
    config_dir = tmp_path / ".ecsctl"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({
        "current": "prod",
        "contexts": {"prod": {"cluster_name": "production", "aws_region": "us-east-1"}},
    }))
    return tmp_path


class TestVersion:
    def test_version_option(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "2.0.0" in result.output


class TestApplyCommand:
    def test_apply_service_dry_run(self, runner, sample_service_yaml, mock_boto3_clients):
        result = runner.invoke(cli, [
            "apply", "-f", sample_service_yaml, "--dry-run", "--cluster", "production"
        ])
        assert result.exit_code == 0
        assert "Applying Service/my-app-service" in result.output
        assert "DRY-RUN" in result.output

    def test_apply_task_definition_dry_run(self, runner, sample_task_definition_yaml, mock_boto3_clients):
        result = runner.invoke(cli, [
            "apply", "-f", sample_task_definition_yaml, "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Applying TaskDefinition/my-app" in result.output

    def test_apply_file_not_found(self, runner, mock_boto3_clients):
        result = runner.invoke(cli, ["apply", "-f", "/nonexistent/file.yaml"])
        assert result.exit_code == 0
        assert "File not found" in result.output

    def test_apply_multiple_files(self, runner, sample_service_yaml, sample_task_definition_yaml, mock_boto3_clients):
        result = runner.invoke(cli, [
            "apply",
            "-f", sample_task_definition_yaml,
            "-f", sample_service_yaml,
            "--dry-run",
            "--cluster", "production",
        ])
        assert result.exit_code == 0
        assert "TaskDefinition" in result.output
        assert "Service" in result.output


class TestGetCommand:
    def test_get_services(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_services.return_value = LIST_SERVICES_RESPONSE
        mock_boto3_clients["ecs"].describe_services.return_value = DESCRIBE_SERVICES_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "service", "--cluster", "production"])
            assert result.exit_code == 0
            assert "my-app-service" in result.output

    def test_get_clusters(self, runner, mock_boto3_clients):
        mock_boto3_clients["ecs"].list_clusters.return_value = LIST_CLUSTERS_RESPONSE
        mock_boto3_clients["ecs"].describe_clusters.return_value = DESCRIBE_CLUSTERS_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "cluster"])
            assert result.exit_code == 0
            assert "production" in result.output

    def test_get_loadbalancers(self, runner, mock_boto3_clients):
        mock_boto3_clients["elbv2"].describe_load_balancers.return_value = DESCRIBE_LOAD_BALANCERS_RESPONSE

        with patch("boto3.client", side_effect=lambda svc, **kw: mock_boto3_clients.get(svc, MagicMock())):
            result = runner.invoke(cli, ["get", "loadbalancer"])
            assert result.exit_code == 0
            assert "api-alb" in result.output

    def test_get_single_resource_yaml(self, runner, mock_boto3_clients):
        with patch("ecsctl.cli.fetch_resource") as mock_fetch:
            from ecsctl.resources.base import ECSResource, Metadata
            mock_fetch.return_value = ECSResource(
                apiVersion="ecs/v1",
                kind="Service",
                metadata=Metadata(name="my-svc", namespace="prod"),
                spec={"desiredCount": 2},
            )
            result = runner.invoke(cli, ["get", "service", "my-svc", "-o", "yaml", "--cluster", "prod"])
            assert result.exit_code == 0
            assert "desiredCount" in result.output


class TestDeleteCommand:
    def test_delete_service_dry_run(self, runner, sample_service_yaml, mock_boto3_clients):
        result = runner.invoke(cli, [
            "delete", "-f", sample_service_yaml, "--dry-run", "--cluster", "production"
        ])
        assert result.exit_code == 0
        assert "Deleting Service/my-app-service" in result.output
        assert "DRY-RUN" in result.output


class TestScaleCommand:
    def test_scale_dry_run(self, runner, mock_boto3_clients):
        result = runner.invoke(cli, [
            "scale", "my-svc", "5", "--dry-run", "--cluster", "production"
        ])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output


class TestConfigCommand:
    def test_config_set(self, runner, tmp_path):
        from pathlib import Path
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, [
                "config", "set", "staging",
                "--cluster-name", "staging-cluster",
                "--aws-region", "us-west-2",
            ])
            assert result.exit_code == 0
            assert "saved" in result.output

    def test_config_context_switch(self, runner, tmp_path):
        from pathlib import Path
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "current": "dev",
            "contexts": {"dev": {}, "prod": {"cluster_name": "production"}},
        }))

        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["config", "context", "prod"])
            assert result.exit_code == 0
            assert "Switched to context 'prod'" in result.output

    def test_config_show(self, runner, tmp_path):
        from pathlib import Path
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "current": "prod",
            "contexts": {"prod": {"cluster_name": "production"}},
        }))

        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["config", "show"])
            assert result.exit_code == 0
