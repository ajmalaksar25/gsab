from setuptools import setup, find_packages

setup(
    name="gsheets_db",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "google-auth-oauthlib>=0.4.6",
        "google-auth>=2.3.3",
        "google-api-python-client>=2.31.0",
        "cryptography>=35.0.0",
        "python-dotenv>=0.19.2",
    ],
    python_requires=">=3.8",
) 