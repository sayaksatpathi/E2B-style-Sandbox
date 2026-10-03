#!/usr/bin/env python3
"""
sandbox CLI — interact with the E2B-style sandbox API.

Usage:
  sandbox create --template python --ttl 300
  sandbox exec <id> python -c "print(2+2)"
  sandbox logs <id>
  sandbox pause <id>
  sandbox resume <id>
  sandbox destroy <id>
  sandbox list
"""

import os
import sys
import json
import typer
import httpx
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(help="E2B-Style Ephemeral Code Sandbox CLI")
console = Console()

API_BASE = os.getenv("SANDBOX_API_URL", "http://localhost:8000")
API_KEY = os.getenv("SANDBOX_API_KEY", "dev-api-key-1")


def get_headers():
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def handle_error(response: httpx.Response):
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        console.print(f"[red]Error {response.status_code}:[/red] {detail}")
        raise typer.Exit(code=1)


@app.command()
def create(
    template: str = typer.Option("python", help="Sandbox template (python|node|bash|go|ruby)"),
    ttl: int = typer.Option(300, help="TTL in seconds"),
    cpu: float = typer.Option(1.0, help="CPU limit (cores)"),
    memory: int = typer.Option(512, help="Memory limit (MB)"),
    network: str = typer.Option("restricted", help="Network policy (none|restricted|full)"),
):
    """Create a new sandbox."""
    with httpx.Client() as client:
        r = client.post(
            f"{API_BASE}/sandboxes",
            headers=get_headers(),
            json={
                "template": template,
                "ttl_seconds": ttl,
                "cpu_limit": cpu,
                "memory_mb": memory,
                "network_policy": network,
            },
            timeout=60,
        )
    handle_error(r)
    data = r.json()
    console.print(f"[green]Sandbox created:[/green] {data['id']}")
    console.print(f"  Status: {data['status']}")
    console.print(f"  Template: {data['template']}")
    console.print(f"  Expires: {data['expires_at']}")
    console.print(f"  CPU: {data['cpu_limit']} cores  Memory: {data['memory_mb']} MB")


@app.command()
def exec(
    sandbox_id: str = typer.Argument(..., help="Sandbox ID"),
    command: str = typer.Argument(..., help="Command to run"),
    args: Optional[List[str]] = typer.Argument(None, help="Command arguments"),
    timeout: int = typer.Option(30, help="Execution timeout in seconds"),
):
    """Execute a command inside a sandbox."""
    with httpx.Client() as client:
        r = client.post(
            f"{API_BASE}/sandboxes/{sandbox_id}/exec",
            headers=get_headers(),
            json={"command": command, "args": args or [], "timeout": timeout},
            timeout=timeout + 15,
        )
    handle_error(r)
    data = r.json()
    if data.get("stdout"):
        console.print(data["stdout"], end="")
    if data.get("stderr"):
        console.print(f"[yellow]{data['stderr']}[/yellow]", end="")
    exit_code = data.get("exit_code", 0)
    console.print(f"\n[dim]exit_code={exit_code}  duration={data['duration_ms']}ms[/dim]")
    raise typer.Exit(code=exit_code)


@app.command()
def logs(
    sandbox_id: str = typer.Argument(..., help="Sandbox ID"),
    tail: int = typer.Option(100, help="Number of log lines"),
):
    """Get logs from a sandbox."""
    with httpx.Client() as client:
        r = client.get(
            f"{API_BASE}/sandboxes/{sandbox_id}/logs",
            headers=get_headers(),
            params={"tail": tail},
            timeout=30,
        )
    handle_error(r)
    console.print(r.json().get("logs", ""))


@app.command()
def pause(sandbox_id: str = typer.Argument(..., help="Sandbox ID")):
    """Pause a running sandbox."""
    with httpx.Client() as client:
        r = client.post(f"{API_BASE}/sandboxes/{sandbox_id}/pause", headers=get_headers(), timeout=30)
    handle_error(r)
    console.print(f"[yellow]Sandbox {sandbox_id} paused.[/yellow]")


@app.command()
def resume(sandbox_id: str = typer.Argument(..., help="Sandbox ID")):
    """Resume a paused sandbox."""
    with httpx.Client() as client:
        r = client.post(f"{API_BASE}/sandboxes/{sandbox_id}/resume", headers=get_headers(), timeout=30)
    handle_error(r)
    console.print(f"[green]Sandbox {sandbox_id} resumed.[/green]")


@app.command()
def destroy(sandbox_id: str = typer.Argument(..., help="Sandbox ID")):
    """Destroy a sandbox."""
    with httpx.Client() as client:
        r = client.delete(f"{API_BASE}/sandboxes/{sandbox_id}", headers=get_headers(), timeout=30)
    handle_error(r)
    console.print(f"[red]Sandbox {sandbox_id} destroyed.[/red]")


@app.command()
def status(sandbox_id: str = typer.Argument(..., help="Sandbox ID")):
    """Get sandbox status."""
    with httpx.Client() as client:
        r = client.get(f"{API_BASE}/sandboxes/{sandbox_id}", headers=get_headers(), timeout=30)
    handle_error(r)
    data = r.json()
    table = Table(title=f"Sandbox {sandbox_id[:8]}...")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for k, v in data.items():
        if k != "user_id":
            table.add_row(k, str(v))
    console.print(table)


@app.command()
def token(user_id: str = typer.Argument(..., help="User ID to issue token for")):
    """Issue a JWT (dev only)."""
    with httpx.Client() as client:
        r = client.post(f"{API_BASE}/auth/token", json={"user_id": user_id}, timeout=10)
    handle_error(r)
    console.print(r.json()["access_token"])


if __name__ == "__main__":
    app()
