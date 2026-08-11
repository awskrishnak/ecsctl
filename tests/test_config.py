"""Tests for ecsctl/config.py - ConfigManager."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from ecsctl.config import ConfigManager


class TestConfigManager:
    def test_init_creates_config_dir(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert (tmp_path / ".ecsctl").exists()

    def test_init_loads_existing_config(self, tmp_path):
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "current": "prod",
            "contexts": {
                "prod": {"cluster_name": "production", "aws_region": "us-east-1"},
            }
        }))

        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert mgr.current == "prod"
            assert mgr.contexts["prod"]["cluster_name"] == "production"

    def test_init_empty_dir(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert mgr.current == "default"
            assert mgr.contexts == {}

    def test_set_context(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            mgr.set_context("staging", cluster_name="staging-cluster", aws_region="us-west-2")
            assert mgr.contexts["staging"]["cluster_name"] == "staging-cluster"
            assert mgr.contexts["staging"]["aws_region"] == "us-west-2"

            # Verify persistence
            config_file = tmp_path / ".ecsctl" / "config.json"
            data = json.loads(config_file.read_text())
            assert "staging" in data["contexts"]

    def test_set_context_skips_none_values(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            mgr.set_context("dev", cluster_name="dev-cluster", aws_profile=None)
            assert "aws_profile" not in mgr.contexts["dev"]

    def test_switch_context(self, tmp_path):
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "current": "dev",
            "contexts": {
                "dev": {"cluster_name": "dev"},
                "prod": {"cluster_name": "production"},
            }
        }))

        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert mgr.current == "dev"
            mgr.switch_context("prod")
            assert mgr.current == "prod"

    def test_switch_context_nonexistent_raises(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            with pytest.raises(ValueError, match="Context nonexistent not found"):
                mgr.switch_context("nonexistent")

    def test_get_current(self, tmp_path):
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "current": "prod",
            "contexts": {
                "prod": {"cluster_name": "production", "aws_region": "us-east-1"},
            }
        }))

        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            current = mgr.get_current()
            assert current == {"cluster_name": "production", "aws_region": "us-east-1"}

    def test_get_current_missing_context_returns_empty(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert mgr.get_current() == {}

    def test_get_cluster_from_context(self, tmp_path):
        config_dir = tmp_path / ".ecsctl"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "current": "prod",
            "contexts": {"prod": {"cluster_name": "production"}},
        }))

        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert mgr.get_cluster() == "production"

    def test_get_cluster_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWS_ECS_CLUSTER_NAME", "env-cluster")
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            # No context set, falls back to env
            assert mgr.get_cluster() == "env-cluster"

    def test_get_cluster_none_when_nothing_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AWS_ECS_CLUSTER_NAME", raising=False)
        with patch.object(Path, "home", return_value=tmp_path):
            mgr = ConfigManager()
            assert mgr.get_cluster() is None
