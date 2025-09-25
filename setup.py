#!/usr/bin/env python3
"""
Setup script for GPTase Multi-Agent Framework
"""

from setuptools import setup, find_packages

setup(
    name="gptase",
    version="1.0.0",
    description="A comprehensive multi-agent framework for AI task automation",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="GPTase Team",
    author_email="team@gptase.com",
    url="https://github.com/gptase/gptase",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        "aiofiles>=23.0.0",
        "httpx>=0.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
        ],
        "web": [
            "fastapi>=0.104.0",
            "uvicorn>=0.24.0",
            "jinja2>=3.1.2",
            "websockets>=11.0.0",
            "python-multipart>=0.0.6",
            "aiohttp>=3.8.0",
        ],
        "models": [
            "openai>=1.0.0",
            "anthropic>=0.28.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "gptase=gptase.main:main",
            "gptase-web=gptase.web.app:create_app",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)