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


def test_skill_list():
    r = runner.invoke(app, ["skill", "list"])
    assert r.exit_code == 0
    assert "gsab" in r.output and "gsab-fastapi" in r.output


def test_skill_install(tmp_path):
    r = runner.invoke(app, ["skill", "install", "--path", str(tmp_path)])
    assert r.exit_code == 0
    assert (tmp_path / "gsab" / "SKILL.md").exists()
    assert (tmp_path / "gsab" / "reference.md").exists()
    assert (tmp_path / "gsab" / "recipes.md").exists()
    assert (tmp_path / "gsab-fastapi" / "SKILL.md").exists()


def test_skill_install_portable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["skill", "install", "--path", str(tmp_path / "skills"), "--portable"])
    assert r.exit_code == 0
    guide = tmp_path / "GSAB_LLMS.md"
    assert guide.exists()
    assert "GSAB" in guide.read_text(encoding="utf-8")


def test_doctor_offline():
    r = runner.invoke(app, ["doctor"])
    assert r.exit_code == 0
    assert "gsab" in r.output  # version + checks; no --live so no network


def test_init_scaffolds(tmp_path):
    r = runner.invoke(app, ["init", str(tmp_path)])
    assert r.exit_code == 0
    assert (tmp_path / "schema.py").exists()
    assert (tmp_path / "app.py").exists()
    assert not (tmp_path / "api.py").exists()


def test_init_fastapi(tmp_path):
    r = runner.invoke(app, ["init", str(tmp_path), "--fastapi"])
    assert r.exit_code == 0
    assert (tmp_path / "api.py").exists()


def test_init_keeps_existing(tmp_path):
    (tmp_path / "app.py").write_text("# mine", encoding="utf-8")
    r = runner.invoke(app, ["init", str(tmp_path)])
    assert r.exit_code == 0
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "# mine"  # not clobbered


def test_cookbook_list_and_show(tmp_path):
    r = runner.invoke(app, ["cookbook", "list"])
    assert r.exit_code == 0
    assert "import_csv" in r.output

    r = runner.invoke(app, ["cookbook", "show", "import_csv", "--out", str(tmp_path / "r.py")])
    assert r.exit_code == 0
    assert (tmp_path / "r.py").exists()

    r = runner.invoke(app, ["cookbook", "show", "nope"])
    assert r.exit_code == 1
