"""Cache management command — Inspect and clear local data."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import rich_argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from remora_fin.services.cache_service import CacheService

logger = logging.getLogger(__name__)
console = Console()


def cache_cmd(args: argparse.Namespace) -> None:
    """Manage local application cache."""
    cache = CacheService()
    action = args.cache_action or "info"

    if action == "clear":
        with console.status("[bold #ff4500]Clearing local cache..."):
            stats_before = cache.get_stats()
            cache.clear()
        
        console.print(Panel(
            f"[bold #39ff14]Success![/]\n\n"
            f"Removed [bold #00f3ff]{stats_before['count']}[/] files.\n"
            f"Freed [bold #00f3ff]{stats_before['size_bytes'] / 1024 / 1024:.2f} MB[/] of disk space.",
            title="[bold #ff4500]Cache Purged[/]",
            border_style="#ff4500"
        ))

    elif action == "info":
        stats = cache.get_stats()
        
        table = Table(title="Local Cache Statistics", border_style="#4b86b4")
        table.add_column("Property", style="bold #4b86b4")
        table.add_column("Value", style="#e6f4f8")
        
        table.add_row("Cache Directory", stats["path"])
        table.add_row("Total Files", str(stats["count"]))
        table.add_row("Total Size", f"{stats['size_bytes'] / 1024 / 1024:.2f} MB")
        table.add_row("Auto-Cleanup", "Enabled (7 days)")
        
        console.print(table)
        console.print("\n[dim #4b86b4]Use 'remora-fin cache clear' to manually delete all files.[/]")

    else:
        # Default to info if no action provided
        stats = cache.get_stats()
        console.print(f"Cache contains [bold]{stats['count']}[/] files ({stats['size_bytes'] / 1024 / 1024:.2f} MB).")


def add_cache_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add cache management subparser."""
    parser = subparsers.add_parser(
        "cache",
        help="Manage local data cache",
        description="Inspect or clear the local Parquet/JSON cache used to speed up analysis.",
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
    )
    
    sub_subparsers = parser.add_subparsers(dest="cache_action", help="Cache actions")
    
    sub_subparsers.add_parser("clear", help="Remove all cached files immediately")
    sub_subparsers.add_parser("info", help="Show cache usage statistics")
    
    parser.set_defaults(func=cache_cmd)
