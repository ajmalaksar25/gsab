"""CLI smoke tests — notably that `gsab help` works like `gsab --help`."""

from typer.testing import CliRunner

from gsab.cli import app

runner = CliRunner()


def test_help_command_shows_usage():
    r = runner.invoke(app, ["help"])
    assert r.exit_code == 0
    assert "Usage" in r.output
    assert "auth" in r.output and "version" in r.output


def test_help_command_for_subcommand():
    r = runner.invoke(app, ["help", "auth"])
    assert r.exit_code == 0
    assert "login" in r.output


def test_help_unknown_command_errors():
    r = runner.invoke(app, ["help", "nope"])
    assert r.exit_code == 1


def test_version():
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert "gsab" in r.output
