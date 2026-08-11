"""Shared pytest fixtures for ecsctl tests."""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config directory for ConfigManager."""
    config_dir = tmp_path / ".ecsctl"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({
        "current": "prod",
        "contexts": {
            "prod": {"cluster_name": "production", "aws_profile": "default", "aws_region": "us-east-1"},
            "staging": {"cluster_name": "staging", "aws_profile": "staging", "aws_region": "us-west-2"},
        }
    }))
    return config_dir


@pytest.fixture
def sample_service_yaml(tmp_path):
    """Create a sample service YAML file."""
    content = """apiVersion: ecs/v1
kind: Service
metadata:
  name: my-app-service
  namespace: production
spec:
  taskDefinition: my-app
  desiredCount: 2
  launchType: FARGATE
  networkConfiguration:
    awsvpcConfiguration:
      subnets:
        - subnet-0123456789abcdef0
      securityGroups:
        - sg-0123456789abcdef0
      assignPublicIp: ENABLED
"""
    p = tmp_path / "service.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_task_definition_yaml(tmp_path):
    """Create a sample task definition YAML file."""
    content = """apiVersion: ecs/v1
kind: TaskDefinition
metadata:
  name: my-app
  namespace: production
spec:
  family: my-app
  networkMode: awsvpc
  requiresCompatibilities:
    - FARGATE
  cpu: "256"
  memory: "512"
  executionRoleArn: arn:aws:iam::123456789012:role/ecsTaskExecutionRole
  containerDefinitions:
    - name: app
      image: nginx:latest
      essential: true
      portMappings:
        - containerPort: 80
          protocol: tcp
"""
    p = tmp_path / "task-definition.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_alb_yaml(tmp_path):
    """Create a sample ALB YAML file."""
    content = """apiVersion: ecs/v1
kind: LoadBalancer
metadata:
  name: api-alb
  namespace: production
spec:
  type: application
  scheme: internet-facing
  subnets:
    - subnet-0123456789abcdef0
    - subnet-0fedcba9876543210
  securityGroups:
    - sg-0123456789abcdef0
  tags:
    Environment: production
"""
    p = tmp_path / "alb.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_asg_yaml(tmp_path):
    """Create a sample ASG YAML file."""
    content = """apiVersion: ecs/v1
kind: AutoScalingGroup
metadata:
  name: ecs-cluster-asg
spec:
  MinSize: 2
  MaxSize: 10
  DesiredCapacity: 3
  VPCZoneIdentifier: subnet-0123456789abcdef0,subnet-0fedcba9876543210
"""
    p = tmp_path / "asg.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_iam_role_yaml(tmp_path):
    """Create a sample IAM role YAML file."""
    content = """apiVersion: ecs/v1
kind: IAMRole
metadata:
  name: ecsTaskRole
spec:
  assumeRolePolicyDocument:
    Version: "2012-10-17"
    Statement:
      - Effect: Allow
        Principal:
          Service: ecs-tasks.amazonaws.com
        Action: sts:AssumeRole
  managedPolicyArns:
    - arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
  inlinePolicies:
    - PolicyName: S3Access
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action:
              - s3:GetObject
            Resource: "arn:aws:s3:::my-bucket/*"
"""
    p = tmp_path / "iam-role.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_acm_yaml(tmp_path):
    """Create a sample ACM YAML file."""
    content = """apiVersion: ecs/v1
kind: Certificate
metadata:
  name: api.example.com
spec:
  domainName: api.example.com
  subjectAlternativeNames:
    - "*.api.example.com"
  validationMethod: DNS
  tags:
    - Key: Environment
      Value: production
"""
    p = tmp_path / "acm.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_cloudmap_yaml(tmp_path):
    """Create a sample CloudMap namespace YAML file."""
    content = """apiVersion: ecs/v1
kind: ServiceDiscoveryNamespace
metadata:
  name: internal.local
spec:
  type: DNS_PRIVATE
  description: Internal namespace
  vpcId: vpc-0123456789abcdef0
"""
    p = tmp_path / "cloudmap.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def mock_boto3_clients():
    """Create mock boto3 clients for all services used by ecsctl."""
    clients = {
        "ecs": MagicMock(),
        "elbv2": MagicMock(),
        "autoscaling": MagicMock(),
        "iam": MagicMock(),
        "acm": MagicMock(),
        "servicediscovery": MagicMock(),
    }

    def fake_client(service, **kwargs):
        return clients.get(service, MagicMock())

    with patch("boto3.client", side_effect=fake_client):
        yield clients
