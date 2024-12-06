"""Setup script for gsheets_db package."""

from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="gsheets_db",
        version="0.1.0",
        packages=find_packages(),
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
        python_requires=">=3.8",
    ) 