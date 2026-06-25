"""GSAB command-line interface.

Entry point declared in pyproject as ``gsab = "gsab.cli:app"``.
"""

from __future__ import annotations

import json
import re
import shutil
from importlib.resources import files
from pathlib import Path
from typing import Optional

import typer

from .. import __version__
from ..auth import FULL_SCOPES
from ..auth import login as _login
from ..auth import logout as _logout
from ..auth import status as _status
from ..exceptions import AuthError, GSABError

app = typer.Typer(
    name="gsab",
    help="Google Sheets as a Backend - auth and manage your sheets from the terminal.",
    no_args_is_help=True,
    add_completion=False,
)

auth_app = typer.Typer(help="Sign in and manage Google credentials.", no_args_is_help=True)
app.add_typer(auth_app, name="auth")


@app.callback()
def _root() -> None:
    """Google Sheets as a Backend - auth and manage your sheets from the terminal."""
    # Quiet, cached (once/day), opt-out-able "a newer gsab is available" notice → stderr.
    from ..utils.update_check import notify_if_outdated

    notify_if_outdated()


@app.command()
def version() -> None:
    """Show the GSAB version."""
    typer.echo(f"gsab {__version__}")


@app.command("help")
def help_cmd(
    ctx: typer.Context,
    command: Optional[str] = typer.Argument(None, help="Show help for this command."),
) -> None:
    """Show help for gsab, or a specific command (same as --help)."""
    group = ctx.parent.command
    if not command:
        typer.echo(ctx.parent.get_help())
        return
    sub = group.get_command(ctx.parent, command)
    if sub is None:
        typer.secho(f"No such command '{command}'. Try `gsab help`.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    # Build a context for the subcommand without importing click directly
    # (typer vendors it): ctx.parent.__class__ is the click Context class.
    sub_ctx = ctx.parent.__class__(sub, info_name=command, parent=ctx.parent)
    typer.echo(sub.get_help(sub_ctx))


@auth_app.command("login")
def auth_login(
    full: bool = typer.Option(
        False,
        "--full",
        help="DIY: request access to ALL your existing sheets (broader, sensitive scope). "
        "Default: only the sheets GSAB creates.",
    ),
    client_secrets: str = typer.Option(
        None, "--client-secrets", "-c", help="DIY: path to your own OAuth client-secrets JSON."
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Print the URL instead of opening a browser."
    ),
) -> None:
    """Sign in with Google (browser) and cache the token for reuse."""
    scopes = FULL_SCOPES if full else None
    try:
        _login(scopes, client_secrets=client_secrets, no_browser=no_browser)
    except AuthError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    mode = "full (all sheets)" if full else "default (GSAB's own sheets)"
    typer.secho(f"Signed in [{mode}]. Token cached.", fg=typer.colors.GREEN)


@auth_app.command("status")
def auth_status(
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """Show which credential sources are available."""
    info = _status()
    if as_json:
        typer.echo(json.dumps(info, indent=2))
        raise typer.Exit()
    state = "logged in" if info["logged_in"] and info["valid"] else "not logged in"
    typer.echo(f"Status:          {state}")
    typer.echo(f"Storage:         {info.get('storage', 'file')}")
    typer.echo(f"Token cache:     {info['token_cache']}")
    typer.echo(f"Service account: {info['service_account'] or '-'}")
    typer.echo(f"Client secrets:  {info['client_secrets'] or '-'}")
    typer.echo(f"gcloud ADC:      {'available' if info['adc_available'] else '-'}")


@auth_app.command("logout")
def auth_logout() -> None:
    """Remove the cached token."""
    if _logout():
        typer.secho("Logged out (token removed).", fg=typer.colors.GREEN)
    else:
        typer.echo("No cached token to remove.")


skill_app = typer.Typer(
    help="Install GSAB skills so your coding agent (Claude Code, etc.) knows how to use GSAB.",
    no_args_is_help=True,
)
app.add_typer(skill_app, name="skill")


def _pkg_dir(name: str) -> Path:
    """Filesystem path to a data directory bundled in the installed package."""
    return Path(str(files("gsab").joinpath(name)))


def _skills_dir() -> Path:
    return _pkg_dir("skills")


def _skill_dirs() -> list[Path]:
    root = _skills_dir()
    return sorted(d for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


def _skill_description(skill_md: Path) -> str:
    """One-line gist from a SKILL.md `description` frontmatter field."""
    text = skill_md.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        fm = text[3:end] if end != -1 else text
        m = re.search(r"description:\s*>?-?\s*\n?\s*(.+)", fm)
        if m:
            return " ".join(m.group(1).split())[:96]
    return ""


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def _portable_guide(skill_dirs: list[Path]) -> str:
    """Concatenate the skills into one paste-into-any-LLM Markdown file."""
    parts = ["# GSAB — skills bundle (paste into ChatGPT, Codex, Cursor or any LLM)\n"]
    for d in skill_dirs:
        for fname in ("SKILL.md", "reference.md", "recipes.md"):
            f = d / fname
            if f.exists():
                parts.append(_strip_frontmatter(f.read_text(encoding="utf-8")).strip())
    return "\n\n---\n\n".join(parts) + "\n"


@skill_app.command("list")
def skill_list() -> None:
    """List the GSAB skills available to install."""
    for d in _skill_dirs():
        typer.echo(f"  {d.name:14} {_skill_description(d / 'SKILL.md')}")


@skill_app.command("install")
def skill_install(
    project: bool = typer.Option(
        False,
        "--project",
        help="Install into ./.claude/skills (this repo) instead of ~/.claude/skills.",
    ),
    portable: bool = typer.Option(
        False,
        "--portable",
        help="Also write GSAB_LLMS.md — one file to paste into ChatGPT/Codex/Cursor/any LLM.",
    ),
    path: Optional[str] = typer.Option(
        None, "--path", help="Install into a custom skills directory."
    ),
) -> None:
    """Install the GSAB skills so your coding agent knows how to use GSAB."""
    if path:
        target = Path(path)
    elif project:
        target = Path.cwd() / ".claude" / "skills"
    else:
        target = Path.home() / ".claude" / "skills"

    skill_dirs = _skill_dirs()
    target.mkdir(parents=True, exist_ok=True)
    for d in skill_dirs:
        dest = target / d.name
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(d, dest)

    typer.secho(f"Installed {len(skill_dirs)} skill(s) to {target}", fg=typer.colors.GREEN)
    for d in skill_dirs:
        typer.echo(f"  • {d.name}")

    if portable:
        out = Path.cwd() / "GSAB_LLMS.md"
        out.write_text(_portable_guide(skill_dirs), encoding="utf-8")
        typer.echo(f"\nWrote {out} — paste it into ChatGPT, Codex, Cursor or any LLM.")

    typer.echo("\nOpen your project in Claude Code; the skills are auto-discovered.")


def _check(label: str, good: bool, detail: str = "") -> None:
    mark = (
        typer.style("OK", fg=typer.colors.GREEN)
        if good
        else typer.style("FAIL", fg=typer.colors.RED)
    )
    typer.echo(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))


@app.command()
def doctor(
    live: bool = typer.Option(
        False, "--live", help="Also do a real create/write/read/delete round-trip."
    ),
) -> None:
    """Check your GSAB setup — and with --live, prove it end to end."""
    import sys

    typer.echo(f"gsab {__version__}  ·  Python {sys.version.split()[0]}")
    info = _status()
    authed = bool(info["logged_in"] and info["valid"])
    _check("authenticated", authed, info.get("storage", "") if authed else "run `gsab auth login`")
    _check("OAuth client available", bool(info["client_secrets"]))
    try:
        import pandas  # noqa: F401

        _check("pandas extra", True)
    except ImportError:
        _check("pandas extra", False, 'optional: pip install "gsab[pandas]"')

    if not live:
        typer.echo("\nRun `gsab doctor --live` for a real read/write round-trip.")
        return
    if not authed:
        typer.secho(
            "Cannot run --live: not authenticated. Run `gsab auth login`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    import asyncio

    from ..core.connection import SheetConnection
    from ..core.schema import Field, FieldType, Schema
    from ..core.sheet_manager import SheetManager

    async def roundtrip() -> list:
        schema = Schema(
            "gsab_doctor",
            [Field("id", FieldType.INTEGER, required=True), Field("note", FieldType.STRING)],
        )
        db = SheetManager(SheetConnection(), schema)
        steps = []
        try:
            sid = await db.create_sheet("gsab doctor (safe to delete)")
            steps.append(("create sheet", True, sid))
            await db.insert({"id": 1, "note": "hello"})
            steps.append(("write", True, ""))
            steps.append(("read", len(await db.read({"id": 1})) == 1, ""))
            steps.append(
                ("server-side query", len(await db.query("SELECT A WHERE A = 1")) == 1, "")
            )
        finally:
            await db.delete_sheet()
            steps.append(("cleanup", True, ""))
        return steps

    typer.echo("\nLive round-trip:")
    try:
        for label, good, detail in asyncio.run(roundtrip()):
            _check(label, good, detail)
    except GSABError as e:
        typer.secho(f"Live check failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    typer.secho("\nAll good — GSAB can read and write your Google Sheets.", fg=typer.colors.GREEN)


@app.command()
def init(
    path: str = typer.Argument(".", help="Directory to scaffold into."),
    fastapi: bool = typer.Option(
        False, "--fastapi", help="Also scaffold a FastAPI CRUD service (api.py)."
    ),
) -> None:
    """Scaffold a runnable GSAB starter project."""
    dest = Path(path)
    dest.mkdir(parents=True, exist_ok=True)
    written, skipped = [], []

    sources = sorted((_pkg_dir("templates") / "starter").iterdir())
    if fastapi:
        sources.append(_pkg_dir("templates") / "fastapi" / "api.py")
    for src in sources:
        if not src.is_file():
            continue
        target = dest / src.name
        if target.exists():
            skipped.append(src.name)
            continue
        target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(src.name)

    typer.secho(f"Scaffolded GSAB project in {dest.resolve()}", fg=typer.colors.GREEN)
    for n in written:
        typer.echo(f"  • {n}")
    for n in skipped:
        typer.echo(f"  • {n} (kept existing)")
    typer.echo("\nNext:\n  gsab auth login")
    typer.echo(
        "  pip install fastapi uvicorn && uvicorn api:app --reload"
        if fastapi
        else "  python app.py"
    )


@app.command("import")
def import_csv(
    csv: str = typer.Argument(..., help="Path to the CSV file."),
    title: str = typer.Option(None, "--title", help="Spreadsheet title (default: the CSV name)."),
) -> None:
    """Load a CSV into a new sheet, inferring a schema. Needs the pandas extra."""
    try:
        import pandas as pd
    except ImportError:
        typer.secho('Needs pandas: pip install "gsab[pandas]"', fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None

    src = Path(csv)
    if not src.exists():
        typer.secho(f"No such file: {csv}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    from ..core.schema import Field, FieldType, Schema

    df = pd.read_csv(src)
    dtype_map = {
        "int64": FieldType.INTEGER,
        "int32": FieldType.INTEGER,
        "float64": FieldType.FLOAT,
        "float32": FieldType.FLOAT,
        "bool": FieldType.BOOLEAN,
    }
    fields = []
    for col in df.columns:
        dt = str(df[col].dtype)
        ftype = FieldType.DATETIME if "datetime" in dt else dtype_map.get(dt, FieldType.STRING)
        fields.append(Field(str(col), ftype, required=False))
    tab = re.sub(r"[^A-Za-z0-9_]+", "_", src.stem) or "data"
    schema = Schema(tab, fields)

    import asyncio

    from ..core.connection import SheetConnection
    from ..core.sheet_manager import SheetManager

    async def run() -> tuple:
        db = SheetManager(SheetConnection(), schema)
        sid = await db.create_sheet(title or src.stem)
        clean = df.where(pd.notnull(df), None)  # NaN -> empty cell
        return sid, await db.from_dataframe(clean)

    try:
        sid, n = asyncio.run(run())
    except GSABError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    typer.secho(f"Imported {n} rows into a new sheet.", fg=typer.colors.GREEN)
    typer.echo(f"  https://docs.google.com/spreadsheets/d/{sid}")


cookbook_app = typer.Typer(help="Ready-to-run GSAB recipes.", no_args_is_help=True)
app.add_typer(cookbook_app, name="cookbook")


def _cookbook_files() -> list[Path]:
    return sorted(f for f in _pkg_dir("cookbook").iterdir() if f.suffix == ".py")


@cookbook_app.command("list")
def cookbook_list() -> None:
    """List available recipes."""
    for f in _cookbook_files():
        typer.echo(f"  {f.stem}")


@cookbook_app.command("show")
def cookbook_show(
    name: str = typer.Argument(..., help="Recipe name (see `gsab cookbook list`)."),
    out: str = typer.Option(
        None, "--out", "-o", help="Write the recipe to a file instead of printing."
    ),
) -> None:
    """Print a recipe, or write it to a file with --out."""
    f = _pkg_dir("cookbook") / f"{name}.py"
    if not f.exists():
        typer.secho(f"No recipe '{name}'. Try `gsab cookbook list`.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    text = f.read_text(encoding="utf-8")
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.secho(f"Wrote {out}", fg=typer.colors.GREEN)
    else:
        typer.echo(text)


if __name__ == "__main__":
    app()
