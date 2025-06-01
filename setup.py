"""
TinyAgent Setup Script
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README file
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="tinyagent",
    version="0.1.0",
    description="A general-purpose, multi-step agent framework with MCP tool integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="TinyAgent Team",
    author_email="team@tinyagent.dev",
    url="https://github.com/your-org/tinyagent",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'tinyagent': [
            'configs/*.yaml',
            'prompts/*.txt',
        ],
    },
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-asyncio>=0.21.0',
            'black>=23.0.0',
            'flake8>=6.0.0',
            'mypy>=1.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'tinyagent=tinyagent.cli.main:main',
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    zip_safe=False,
) 