from setuptools import setup, find_packages

setup(
    name="mcp-firewall",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "mcp-firewall=mcp_firewall.cli:main",
        ],
    },
)
