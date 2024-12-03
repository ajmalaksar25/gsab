from setuptools import setup, find_packages

setup(
    name="gsheets-db",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-auth-oauthlib>=0.4.6",
        "google-auth>=2.3.3",
        "google-api-python-client>=2.0.0",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-multipart>=0.0.5",
        "jinja2>=3.0.0",
        "aiofiles>=0.8.0",
        "cryptography>=3.4.7",
        "python-dotenv>=0.19.0",
    ],
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python library for using Google Sheets as a database backend",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gsheets-db",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.7",
) 