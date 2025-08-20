"""Console utilities for AI processor with rich formatting."""
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from typing import Dict, Any
import logging


def get_console() -> Console:
    """Get a rich console instance."""
    return Console()


def get_progress_bar(show_speed: bool = False):
    """Get a rich progress bar."""
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed} of {task.total})"),
    ]
    
    if show_speed:
        columns.append(TextColumn("• {task.fields[speed]}", style="blue"))
    
    columns.append(TimeRemainingColumn())
    
    return Progress(*columns, console=get_console())


def create_header(title: str, subtitle: str = "") -> Panel:
    """Create a beautiful header panel."""
    if subtitle:
        content = f"[bold white]{title}[/bold white]\n[dim]{subtitle}[/dim]"
    else:
        content = f"[bold white]{title}[/bold white]"
    
    return Panel(
        Align.center(content),
        style="blue",
        padding=(1, 2),
        title="[bold]🤖 AI Processor[/bold]",
        title_align="left"
    )


def create_summary_table(data: Dict[str, Any]) -> Table:
    """Create a summary table."""
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    for key, value in data.items():
        table.add_row(key, str(value))
    
    return table


def print_banner(text: str):
    """Print a banner with the given text."""
    console = get_console()
    console.print(f"\n[bold blue]{'='*60}[/bold blue]")
    console.print(f"[bold white]{text.center(60)}[/bold white]")
    console.print(f"[bold blue]{'='*60}[/bold blue]\n")


def print_success(message: str):
    """Print a success message."""
    console = get_console()
    console.print(f"[bold green]✅ {message}[/bold green]")


def print_warning(message: str):
    """Print a warning message."""
    console = get_console()
    console.print(f"[yellow]⚠️ {message}[/yellow]")


def print_error(message: str):
    """Print an error message."""
    console = get_console()
    console.print(f"[bold red]❌ {message}[/bold red]")


def print_info(title: str, message: str = ""):
    """Print an info message."""
    console = get_console()
    if message:
        console.print(f"[bold cyan]ℹ️ {title}:[/bold cyan] {message}")
    else:
        console.print(f"[bold cyan]ℹ️ {title}[/bold cyan]")


def log_message(message: str, level: str = "info"):
    """Log a message with the appropriate level."""
    if level == "info":
        logging.info(message)
        print_info(message)
    elif level == "warning":
        logging.warning(message)
        print_warning(message)
    elif level == "error":
        logging.error(message)
        print_error(message)
    elif level == "success":
        logging.info(message)
        print_success(message)
    else:
        logging.info(message)
        get_console().print(message)
