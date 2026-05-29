import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def tmp_output_dir():
    """Fixture providing a temporary directory for output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
