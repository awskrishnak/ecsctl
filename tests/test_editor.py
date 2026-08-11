"""Tests for ecsctl/editor.py - Diff calculation and edit flow."""

import pytest
from ecsctl.resources.base import ECSResource, Metadata
from ecsctl.editor import calculate_diff


class TestCalculateDiff:
    def test_no_changes(self):
        resource = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc", namespace="prod"),
            spec={"desiredCount": 2, "taskDefinition": "app:1"},
        )
        diff = calculate_diff(resource, resource)
        assert diff == {}

    def test_spec_change_detected(self):
        old = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={"desiredCount": 2, "taskDefinition": "app:1"},
        )
        new = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={"desiredCount": 5, "taskDefinition": "app:2"},
        )
        diff = calculate_diff(old, new)
        assert "spec" in diff
        assert "desiredCount" in diff["spec"]
        assert diff["spec"]["desiredCount"]["old"] == 2
        assert diff["spec"]["desiredCount"]["new"] == 5
        assert diff["spec"]["taskDefinition"]["old"] == "app:1"
        assert diff["spec"]["taskDefinition"]["new"] == "app:2"

    def test_metadata_change_detected(self):
        old = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc", namespace="dev"),
            spec={"desiredCount": 2},
        )
        new = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc", namespace="prod"),
            spec={"desiredCount": 2},
        )
        diff = calculate_diff(old, new)
        assert "metadata" in diff

    def test_added_spec_field(self):
        old = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={"desiredCount": 2},
        )
        new = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={"desiredCount": 2, "forceNewDeployment": True},
        )
        diff = calculate_diff(old, new)
        assert "spec" in diff
        assert "forceNewDeployment" in diff["spec"]
        assert diff["spec"]["forceNewDeployment"]["old"] is None
        assert diff["spec"]["forceNewDeployment"]["new"] is True

    def test_removed_spec_field(self):
        old = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={"desiredCount": 2, "platformVersion": "LATEST"},
        )
        new = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={"desiredCount": 2},
        )
        diff = calculate_diff(old, new)
        assert "spec" in diff
        assert "platformVersion" in diff["spec"]
        assert diff["spec"]["platformVersion"]["old"] == "LATEST"
        assert diff["spec"]["platformVersion"]["new"] is None
