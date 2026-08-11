"""
AWS CLI skeleton-based response fixtures for testing.
These match the real AWS API response shapes as produced by:
  aws <service> <action> --generate-cli-skeleton output
"""

# =============================================================================
# ECS Responses
# =============================================================================

REGISTER_TASK_DEFINITION_RESPONSE = {
    "taskDefinition": {
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/my-app:1",
        "containerDefinitions": [
            {
                "name": "app",
                "image": "nginx:latest",
                "cpu": 0,
                "memory": None,
                "memoryReservation": None,
                "portMappings": [
                    {"containerPort": 80, "hostPort": 80, "protocol": "tcp"}
                ],
                "essential": True,
                "environment": [],
                "mountPoints": [],
                "volumesFrom": [],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/my-app",
                        "awslogs-region": "us-east-1",
                        "awslogs-stream-prefix": "ecs",
                    },
                },
            }
        ],
        "family": "my-app",
        "taskRoleArn": None,
        "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        "networkMode": "awsvpc",
        "revision": 1,
        "volumes": [],
        "status": "ACTIVE",
        "requiresAttributes": [],
        "placementConstraints": [],
        "compatibilities": ["EC2", "FARGATE"],
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "registeredAt": "2025-01-01T00:00:00.000Z",
        "registeredBy": "arn:aws:iam::123456789012:user/admin",
    }
}

DESCRIBE_SERVICES_RESPONSE = {
    "services": [
        {
            "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/production/my-app-service",
            "serviceName": "my-app-service",
            "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/production",
            "loadBalancers": [],
            "serviceRegistries": [],
            "status": "ACTIVE",
            "desiredCount": 2,
            "runningCount": 2,
            "pendingCount": 0,
            "launchType": "FARGATE",
            "platformVersion": "LATEST",
            "platformFamily": "Linux",
            "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/my-app:1",
            "deploymentConfiguration": {
                "deploymentCircuitBreaker": {"enable": False, "rollback": False},
                "maximumPercent": 200,
                "minimumHealthyPercent": 100,
            },
            "deployments": [
                {
                    "id": "ecs-svc/1234567890",
                    "status": "PRIMARY",
                    "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/my-app:1",
                    "desiredCount": 2,
                    "runningCount": 2,
                    "pendingCount": 0,
                    "launchType": "FARGATE",
                }
            ],
            "events": [],
            "createdAt": "2025-01-01T00:00:00.000Z",
            "createdBy": "arn:aws:iam::123456789012:user/admin",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": ["subnet-0123456789abcdef0"],
                    "securityGroups": ["sg-0123456789abcdef0"],
                    "assignPublicIp": "ENABLED",
                }
            },
        }
    ],
    "failures": [],
}

DESCRIBE_SERVICES_EMPTY = {"services": [], "failures": []}

DESCRIBE_SERVICES_INACTIVE = {
    "services": [
        {
            "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/production/my-app-service",
            "serviceName": "my-app-service",
            "status": "INACTIVE",
            "desiredCount": 0,
            "runningCount": 0,
            "pendingCount": 0,
        }
    ],
    "failures": [],
}

LIST_CLUSTERS_RESPONSE = {
    "clusterArns": [
        "arn:aws:ecs:us-east-1:123456789012:cluster/production",
        "arn:aws:ecs:us-east-1:123456789012:cluster/staging",
    ]
}

DESCRIBE_CLUSTERS_RESPONSE = {
    "clusters": [
        {
            "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/production",
            "clusterName": "production",
            "status": "ACTIVE",
            "registeredContainerInstancesCount": 3,
            "runningTasksCount": 5,
            "pendingTasksCount": 0,
            "activeServicesCount": 2,
            "statistics": [],
            "settings": [],
            "attachments": [],
        }
    ],
    "failures": [],
}

LIST_SERVICES_RESPONSE = {
    "serviceArns": [
        "arn:aws:ecs:us-east-1:123456789012:service/production/my-app-service"
    ]
}

LIST_TASK_DEFINITION_FAMILIES_RESPONSE = {"families": ["my-app", "worker"]}

LIST_TASKS_RESPONSE = {
    "taskArns": ["arn:aws:ecs:us-east-1:123456789012:task/production/abc123"]
}

DESCRIBE_TASKS_RESPONSE = {
    "tasks": [
        {
            "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/production/abc123",
            "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/my-app:1",
            "lastStatus": "RUNNING",
            "startedAt": "2025-01-01T00:00:00.000Z",
        }
    ]
}

DESCRIBE_TASK_DEFINITION_RESPONSE = {
    "taskDefinition": {
        "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/my-app:1",
        "family": "my-app",
        "networkMode": "awsvpc",
        "revision": 1,
        "status": "ACTIVE",
        "requiresAttributes": [{"name": "com.amazonaws.ecs.capability.logging-driver.awslogs"}],
        "compatibilities": ["EC2", "FARGATE"],
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "containerDefinitions": [
            {
                "name": "app",
                "image": "nginx:latest",
                "essential": True,
                "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
            }
        ],
        "registeredAt": "2025-01-01T00:00:00.000Z",
        "registeredBy": "arn:aws:iam::123456789012:user/admin",
    }
}

# =============================================================================
# ELBv2 Responses
# =============================================================================

DESCRIBE_LOAD_BALANCERS_RESPONSE = {
    "LoadBalancers": [
        {
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/api-alb/1234567890",
            "DNSName": "api-alb-123456.us-east-1.elb.amazonaws.com",
            "CanonicalHostedZoneId": "Z35SXDOTRQ7X7K",
            "CreatedTime": "2025-01-01T00:00:00.000Z",
            "LoadBalancerName": "api-alb",
            "Scheme": "internet-facing",
            "VpcId": "vpc-0123456789abcdef0",
            "State": {"Code": "active", "Reason": ""},
            "Type": "application",
            "AvailabilityZones": [
                {"ZoneName": "us-east-1a", "SubnetId": "subnet-0123456789abcdef0"}
            ],
            "SecurityGroups": ["sg-0123456789abcdef0"],
            "IpAddressType": "ipv4",
        }
    ]
}

DESCRIBE_LOAD_BALANCERS_EMPTY = {"LoadBalancers": []}

DESCRIBE_LISTENERS_RESPONSE = {
    "Listeners": [
        {
            "ListenerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:listener/app/api-alb/1234567890/abcdef",
            "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/api-alb/1234567890",
            "Port": 80,
            "Protocol": "HTTP",
            "DefaultActions": [{"Type": "forward", "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/my-tg/1234567890"}],
        }
    ]
}

# =============================================================================
# AutoScaling Responses
# =============================================================================

DESCRIBE_AUTO_SCALING_GROUPS_RESPONSE = {
    "AutoScalingGroups": [
        {
            "AutoScalingGroupName": "ecs-cluster-asg",
            "AutoScalingGroupARN": "arn:aws:autoscaling:us-east-1:123456789012:autoScalingGroup:uuid:autoScalingGroupName/ecs-cluster-asg",
            "LaunchTemplate": {
                "LaunchTemplateId": "lt-0123456789abcdef0",
                "LaunchTemplateName": "ecs-optimized",
                "Version": "$Latest",
            },
            "MinSize": 2,
            "MaxSize": 10,
            "DesiredCapacity": 3,
            "DefaultCooldown": 300,
            "AvailabilityZones": ["us-east-1a", "us-east-1b"],
            "HealthCheckType": "EC2",
            "HealthCheckGracePeriod": 300,
            "Instances": [
                {"InstanceId": "i-0123456789abcdef0", "LifecycleState": "InService", "HealthStatus": "Healthy"},
                {"InstanceId": "i-0fedcba9876543210", "LifecycleState": "InService", "HealthStatus": "Healthy"},
                {"InstanceId": "i-0111111111111111a", "LifecycleState": "InService", "HealthStatus": "Healthy"},
            ],
            "CreatedTime": "2025-01-01T00:00:00.000Z",
            "SuspendedProcesses": [],
            "VPCZoneIdentifier": "subnet-0123456789abcdef0,subnet-0fedcba9876543210",
            "EnabledMetrics": [],
            "Tags": [
                {"Key": "Name", "Value": "ecs-node", "PropagateAtLaunch": True}
            ],
            "TerminationPolicies": ["Default"],
            "TargetGroupARNs": [],
        }
    ]
}

DESCRIBE_AUTO_SCALING_GROUPS_EMPTY = {"AutoScalingGroups": []}

# =============================================================================
# IAM Responses
# =============================================================================

GET_ROLE_RESPONSE = {
    "Role": {
        "RoleName": "ecsTaskRole",
        "RoleId": "AROA1234567890EXAMPLE",
        "Arn": "arn:aws:iam::123456789012:role/ecsTaskRole",
        "Path": "/",
        "AssumeRolePolicyDocument": '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}',
        "CreateDate": "2025-01-01T00:00:00Z",
        "MaxSessionDuration": 3600,
        "RoleLastUsed": {},
    }
}

LIST_ATTACHED_ROLE_POLICIES_RESPONSE = {
    "AttachedPolicies": [
        {
            "PolicyName": "CloudWatchLogsFullAccess",
            "PolicyArn": "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        }
    ]
}

LIST_ROLE_POLICIES_RESPONSE = {"PolicyNames": ["S3Access"]}

GET_ROLE_POLICY_RESPONSE = {
    "RoleName": "ecsTaskRole",
    "PolicyName": "S3Access",
    "PolicyDocument": {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": "arn:aws:s3:::my-bucket/*",
            }
        ],
    },
}

LIST_ROLES_RESPONSE = {
    "Roles": [
        {
            "RoleName": "ecsTaskRole",
            "Arn": "arn:aws:iam::123456789012:role/ecsTaskRole",
            "CreateDate": "2025-01-01T00:00:00Z",
            "Path": "/",
            "AssumeRolePolicyDocument": "{}",
        }
    ]
}

# =============================================================================
# ACM Responses
# =============================================================================

LIST_CERTIFICATES_RESPONSE = {
    "CertificateSummaryList": [
        {
            "CertificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/abc-123",
            "DomainName": "api.example.com",
        }
    ]
}

LIST_CERTIFICATES_EMPTY = {"CertificateSummaryList": []}

DESCRIBE_CERTIFICATE_RESPONSE = {
    "Certificate": {
        "CertificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/abc-123",
        "DomainName": "api.example.com",
        "SubjectAlternativeNames": ["api.example.com", "*.api.example.com"],
        "Status": "ISSUED",
        "Serial": "00:00:00:00:00:00:00:00",
        "Subject": "CN=api.example.com",
        "NotBefore": "2025-01-01T00:00:00Z",
        "NotAfter": "2026-01-01T00:00:00Z",
        "KeyAlgorithm": "RSA-2048",
        "SignatureAlgorithm": "SHA256WITHRSA",
        "InUseBy": [],
        "CreatedAt": "2025-01-01T00:00:00Z",
        "DomainValidationOptions": [],
    }
}

REQUEST_CERTIFICATE_RESPONSE = {
    "CertificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/new-cert-123"
}

# =============================================================================
# ServiceDiscovery Responses
# =============================================================================

LIST_NAMESPACES_RESPONSE = {
    "Namespaces": [
        {
            "Id": "ns-abc123",
            "Arn": "arn:aws:servicediscovery:us-east-1:123456789012:namespace/ns-abc123",
            "Name": "internal.local",
            "Type": "DNS_PRIVATE",
            "CreateDate": "2025-01-01T00:00:00Z",
            "CreatorRequestId": "req-123",
        }
    ]
}

LIST_NAMESPACES_EMPTY = {"Namespaces": []}

LIST_SERVICES_SD_RESPONSE = {
    "Services": [
        {
            "Id": "srv-abc123",
            "Arn": "arn:aws:servicediscovery:us-east-1:123456789012:service/srv-abc123",
            "Name": "api-service",
            "CreateDate": "2025-01-01T00:00:00Z",
            "CreatorRequestId": "req-456",
            "NamespaceId": "ns-abc123",
        }
    ]
}

LIST_SERVICES_SD_EMPTY = {"Services": []}
