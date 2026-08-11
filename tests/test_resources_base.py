"""Tests for ecsctl/resources/base.py - ECSResource model."""

import pytest
import yaml
from ecsctl.resources.base import ECSResource, Metadata


class TestMetadata:
    def test_metadata_defaults(self):
        m = Metadata(name="test")
        assert m.name == "test"
        assert m.namespace is None
        assert m.labels == {}
        assert m.annotations == {}

    def test_metadata_full(self):
        m = Metadata(
            name="my-svc",
            namespace="production",
            labels={"app": "web"},
            annotations={"roleType": "task"},
        )
        assert m.name == "my-svc"
        assert m.namespace == "production"
        assert m.labels == {"app": "web"}
        assert m.annotations == {"roleType": "task"}


class TestECSResourceFromDict:
    def test_minimal_resource(self):
        data = {
            "kind": "Service",
            "metadata": {"name": "my-svc"},
            "spec": {"desiredCount": 2},
        }
        r = ECSResource.from_dict(data)
        assert r.kind == "Service"
        assert r.apiVersion == "ecs/v1"
        assert r.metadata.name == "my-svc"
        assert r.metadata.namespace is None
        assert r.spec == {"desiredCount": 2}

    def test_full_resource(self):
        data = {
            "apiVersion": "ecs/v1",
            "kind": "TaskDefinition",
            "metadata": {
                "name": "my-app",
                "namespace": "production",
                "labels": {"env": "prod"},
                "annotations": {"note": "important"},
            },
            "spec": {
                "family": "my-app",
                "cpu": "256",
                "memory": "512",
            },
        }
        r = ECSResource.from_dict(data)
        assert r.apiVersion == "ecs/v1"
        assert r.kind == "TaskDefinition"
        assert r.metadata.name == "my-app"
        assert r.metadata.namespace == "production"
        assert r.metadata.labels == {"env": "prod"}
        assert r.metadata.annotations == {"note": "important"}
        assert r.spec["family"] == "my-app"

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="Empty manifest"):
            ECSResource.from_dict({})

    def test_none_raises(self):
        with pytest.raises(ValueError, match="Empty manifest"):
            ECSResource.from_dict(None)

    def test_missing_kind_raises(self):
        with pytest.raises(KeyError):
            ECSResource.from_dict({"metadata": {"name": "x"}, "spec": {}})

    def test_missing_metadata_uses_defaults(self):
        data = {"kind": "Cluster", "spec": {"clusterName": "test"}}
        r = ECSResource.from_dict(data)
        assert r.metadata.name == ""
        assert r.metadata.namespace is None

    def test_missing_spec_uses_empty_dict(self):
        data = {"kind": "Service", "metadata": {"name": "svc"}}
        r = ECSResource.from_dict(data)
        assert r.spec == {}


class TestECSResourceToDict:
    def test_minimal_to_dict(self):
        r = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="my-svc"),
            spec={"desiredCount": 2},
        )
        d = r.to_dict()
        assert d == {
            "apiVersion": "ecs/v1",
            "kind": "Service",
            "metadata": {"name": "my-svc"},
            "spec": {"desiredCount": 2},
        }

    def test_full_to_dict_includes_namespace(self):
        r = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="my-svc", namespace="prod"),
            spec={"desiredCount": 2},
        )
        d = r.to_dict()
        assert d["metadata"]["namespace"] == "prod"

    def test_full_to_dict_includes_labels_annotations(self):
        r = ECSResource(
            apiVersion="ecs/v1",
            kind="IAMRole",
            metadata=Metadata(
                name="role", labels={"team": "platform"}, annotations={"note": "x"}
            ),
            spec={},
        )
        d = r.to_dict()
        assert d["metadata"]["labels"] == {"team": "platform"}
        assert d["metadata"]["annotations"] == {"note": "x"}

    def test_empty_labels_not_in_output(self):
        r = ECSResource(
            apiVersion="ecs/v1",
            kind="Service",
            metadata=Metadata(name="svc"),
            spec={},
        )
        d = r.to_dict()
        assert "labels" not in d["metadata"]
        assert "annotations" not in d["metadata"]


class TestECSResourceFromYaml:
    def test_from_yaml_service(self, sample_service_yaml):
        r = ECSResource.from_yaml(sample_service_yaml)
        assert r.kind == "Service"
        assert r.metadata.name == "my-app-service"
        assert r.metadata.namespace == "production"
        assert r.spec["taskDefinition"] == "my-app"
        assert r.spec["desiredCount"] == 2

    def test_from_yaml_task_definition(self, sample_task_definition_yaml):
        r = ECSResource.from_yaml(sample_task_definition_yaml)
        assert r.kind == "TaskDefinition"
        assert r.metadata.name == "my-app"
        assert r.spec["family"] == "my-app"
        assert r.spec["cpu"] == "256"
        assert len(r.spec["containerDefinitions"]) == 1

    def test_from_yaml_iam_role(self, sample_iam_role_yaml):
        r = ECSResource.from_yaml(sample_iam_role_yaml)
        assert r.kind == "IAMRole"
        assert r.metadata.name == "ecsTaskRole"
        assert "assumeRolePolicyDocument" in r.spec
        assert len(r.spec["managedPolicyArns"]) == 1
        assert len(r.spec["inlinePolicies"]) == 1


class TestECSResourceToYaml:
    def test_roundtrip(self):
        original = {
            "apiVersion": "ecs/v1",
            "kind": "Service",
            "metadata": {"name": "my-svc", "namespace": "prod"},
            "spec": {"desiredCount": 3, "taskDefinition": "app:1"},
        }
        r = ECSResource.from_dict(original)
        yaml_str = r.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert parsed["kind"] == "Service"
        assert parsed["metadata"]["name"] == "my-svc"
        assert parsed["spec"]["desiredCount"] == 3
