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
from ..exceptions import AuthError

app = typer.Typer(
    name="gsab",
    help="Google Sheets as a Backend - auth and manage your sheets from the terminal.",
    no_args_is_help=True,
    add_completion=False,
)

auth_app = typer.Typer(help="Sign in and manage Google credentials.", no_args_is_help=True)
app.add_typer(auth_app, name="auth")


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


def _skills_dir() -> Path:
    """Filesystem path to the skills bundled in the installed package."""
    return Path(str(files("gsab").joinpath("skills")))


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


if __name__ == "__main__":
    app()
