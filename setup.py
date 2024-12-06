from setuptools import setup, find_packages

setup(
    name="gsheets_db",
    version="0.1.0",
    packages=find_packages(include=['gsheets_db', 'gsheets_db.*']),
    install_requires=[
        "google-auth-oauthlib>=0.4.6",
        "google-auth-httplib2>=0.1.0",
        "google-api-python-client>=2.0.0",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-multipart>=0.0.5",
        "jinja2>=3.0.0",
        "aiofiles>=0.8.0",
        "cryptography>=3.4.7",
        "python-dotenv>=0.19.0",
        "cryptography>=3.4.7",
    ],
    author="Ajmal Aksar",
    author_email="ajmalaksar25@gmail.com",
    description="A Python library for using Google Sheets as a database backend",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/ajmalaksar/gsheets_db",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.8",
    extras_require={
        'test': [
            'pytest>=6.0.0',
            'pytest-asyncio>=0.15.0',
            'pytest-cov>=2.12.0',
        ],
    },
) 