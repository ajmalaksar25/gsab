"""Setup script for gsab package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gsab",
    version="0.1.0",
    author="Ajmal Aksar",
    author_email="ajmalaksar25@gmail.com",
    description="A database-like interface for Google Sheets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ajmalaksar25/gsab",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "google-auth-oauthlib>=0.4.6",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-multipart>=0.0.5",
        "jinja2>=3.0.0",
        "aiofiles>=0.8.0",
        "pytest>=6.0.0",
        "pytest-asyncio>=0.15.0",
        "pytest-cov>=2.12.0",
        "google-auth>=2.3.3",
        "google-api-python-client>=2.31.0",
        "cryptography>=35.0.0",
        "python-dotenv>=0.19.2",
    ],
) 