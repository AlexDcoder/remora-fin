import argparse
import rich_argparse
from textwrap import dedent

def execute_cli():
    parser = argparse.ArgumentParser(
        prog="remora",
        description="Remora-Fin: AWS FinOps (CLI)",
        epilog=dedent(
            """
            [bold blue]Remora[/] is a lightweight, high-performance FinOps toolkit for AWS.
            """
        ),
    )


    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser.add_argument("-v", "--version", action="version", version="[blue]remora[/] [bold green]v0.1.0[/]")
    
    args = parser.parse_args()

if __name__ == "__main__":
    execute_cli()