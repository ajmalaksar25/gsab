import os

# Never reach out to PyPI for the "update available" notice during tests.
os.environ.setdefault("GSAB_NO_UPDATE_CHECK", "1")
