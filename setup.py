from setuptools import setup, find_packages

setup(
    name="ecsctl",
    version="2.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "boto3>=1.20",
        "PyYAML>=6.0",
        "tabulate>=0.9",
        "python-dateutil>=2.8",
    ],
    entry_points={
        "console_scripts": [
            "ecsctl=ecsctl.cli:cli",
        ],
    },
    python_requires=">=3.8",
    author="10clouds-enhanced",
    description="kubectl-style CLI for AWS ECS and infrastructure",
)
