import os
import json
from pathlib import Path
import boto3


class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".ecsctl"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        self.contexts = {}
        self.current = "default"
        self._load()
        self._session = None

    def _load(self):
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.contexts = data.get("contexts", {})
                self.current = data.get("current", "default")

    def _save(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"current": self.current, "contexts": self.contexts}, f, indent=2)

    def set_context(self, name, **kwargs):
        self.contexts[name] = {k: v for k, v in kwargs.items() if v is not None}
        self._save()

    def switch_context(self, name):
        if name not in self.contexts:
            raise ValueError(f"Context {name} not found")
        self.current = name
        self._save()

    def get_current(self):
        return self.contexts.get(self.current, {})

    def get_cluster(self):
        return self.get_current().get("cluster_name") or os.getenv("AWS_ECS_CLUSTER_NAME")

    def get_session(self):
        if self._session is None:
            ctx = self.get_current()
            kwargs = {}
            profile = ctx.get("aws_profile")
            region = ctx.get("aws_region")
            if profile:
                kwargs["profile_name"] = profile
            if region:
                kwargs["region_name"] = region
            self._session = boto3.Session(**kwargs)
        return self._session
