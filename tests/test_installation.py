import subprocess
import sys
import pytest
import os

def test_package_installation():
    """Test package installation."""
    # Test dependencies first
    import google.oauth2
    import cryptography
    
    # Test import
    import gsab
    assert hasattr(gsab, "__version__")
    
    # Skip pip installation test if running in CI
    if os.environ.get("CI"):
        pytest.skip("Skipping pip installation in CI environment")
    
    # Test pip installation with proper encoding
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True  # This will raise CalledProcessError if returncode != 0
        )
        assert result.returncode == 0
    except UnicodeDecodeError:
        # Handle encoding issues on Windows
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            encoding='utf-8',
            errors='ignore'  # Ignore encoding errors
        )
        assert result.returncode == 0