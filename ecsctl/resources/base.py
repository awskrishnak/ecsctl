from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import yaml


@dataclass
class Metadata:
    name: str
    namespace: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class ECSResource:
    apiVersion: str
    kind: str
    metadata: Metadata
    spec: Dict[str, Any]

    @classmethod
    def from_yaml(cls, path: str) -> "ECSResource":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "ECSResource":
        if not data:
            raise ValueError("Empty manifest")
        meta = data.get("metadata", {})
        return cls(
            apiVersion=data.get("apiVersion", "ecs/v1"),
            kind=data["kind"],
            metadata=Metadata(
                name=meta.get("name", ""),
                namespace=meta.get("namespace"),
                labels=meta.get("labels", {}),
                annotations=meta.get("annotations", {}),
            ),
            spec=data.get("spec", {}),
        )

    def to_dict(self) -> dict:
        result = {
            "apiVersion": self.apiVersion,
            "kind": self.kind,
            "metadata": {"name": self.metadata.name},
            "spec": self.spec,
        }
        if self.metadata.namespace:
            result["metadata"]["namespace"] = self.metadata.namespace
        if self.metadata.labels:
            result["metadata"]["labels"] = self.metadata.labels
        if self.metadata.annotations:
            result["metadata"]["annotations"] = self.metadata.annotations
        return result

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False, allow_unicode=True)
