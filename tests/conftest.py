import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
import shutil
from src.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_data_dir():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def cli_app(runner, temp_data_dir):
    def run_cli(args, input=None):
        full_args = ['--data-dir', str(temp_data_dir)] + args
        return runner.invoke(cli, full_args, input=input)
    return run_cli