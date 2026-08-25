"""Tests for ecsctl/output.py - OutputFormatter table/json/yaml."""

import json
import yaml
import pytest
from ecsctl.output import OutputFormatter


class TestOutputFormatterJson:
    def test_prints_json(self, capsys):
        f = OutputFormatter("json")
        f.print({"name": "my-svc", "count": 3})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["name"] == "my-svc"
        assert parsed["count"] == 3

    def test_prints_json_list(self, capsys):
        f = OutputFormatter("json")
        f.print([{"a": 1}, {"a": 2}])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed) == 2

    def test_dumps_json(self):
        f = OutputFormatter("json")
        result = f.dumps({"key": "value"})
        parsed = json.loads(result)
        assert parsed["key"] == "value"


class TestOutputFormatterYaml:
    def test_prints_yaml(self, capsys):
        f = OutputFormatter("yaml")
        f.print({"name": "my-svc", "count": 3})
        captured = capsys.readouterr()
        parsed = yaml.safe_load(captured.out)
        assert parsed["name"] == "my-svc"
        assert parsed["count"] == 3

    def test_prints_yaml_list(self, capsys):
        f = OutputFormatter("yaml")
        f.print([{"name": "a"}, {"name": "b"}])
        captured = capsys.readouterr()
        parsed = yaml.safe_load(captured.out)
        assert len(parsed) == 2

    def test_dumps_yaml(self):
        f = OutputFormatter("yaml")
        result = f.dumps({"key": "value"})
        parsed = yaml.safe_load(result)
        assert parsed["key"] == "value"


class TestOutputFormatterTable:
    def test_prints_table_from_list_of_dicts(self, capsys):
        f = OutputFormatter("table")
        data = [
            {"name": "svc-1", "status": "ACTIVE", "count": 2},
            {"name": "svc-2", "status": "DRAINING", "count": 0},
        ]
        f.print(data)
        captured = capsys.readouterr()
        assert "svc-1" in captured.out
        assert "svc-2" in captured.out
        assert "ACTIVE" in captured.out
        assert "NAME" in captured.out  # header

    def test_prints_table_from_dict(self, capsys):
        f = OutputFormatter("table")
        f.print({"key1": "val1", "key2": "val2"})
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "val1" in captured.out

    def test_prints_plain_string(self, capsys):
        f = OutputFormatter("table")
        f.print("just a string")
        captured = capsys.readouterr()
        assert "just a string" in captured.out

    def test_dumps_table_returns_string(self):
        f = OutputFormatter("table")
        result = f.dumps({"key": "val"})
        assert "key" in result


class TestOutputFormatterCaseInsensitive:
    def test_json_uppercase(self, capsys):
        f = OutputFormatter("JSON")
        f.print({"x": 1})
        captured = capsys.readouterr()
        assert json.loads(captured.out)["x"] == 1

    def test_yaml_uppercase(self, capsys):
        f = OutputFormatter("YAML")
        f.print({"x": 1})
        captured = capsys.readouterr()
        assert yaml.safe_load(captured.out)["x"] == 1
