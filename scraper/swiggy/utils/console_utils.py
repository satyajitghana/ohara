"""Console output utilities."""
from rich.console import Console
from rich.progress import (
    Progress, 
    BarColumn, 
    TextColumn, 
    TimeRemainingColumn,
    MofNCompleteColumn,
    SpinnerColumn,
    TaskProgressColumn
)
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align
import time
from typing import Optional


# Global console instance
_console = Console(force_terminal=True, width=120)


def get_console() -> Console:
    """Get a Rich console instance."""
    return _console


def get_progress_bar(show_speed: bool = True) -> Progress:
    """Get a beautifully configured progress bar."""
    columns = [
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}", justify="left"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        "•",
        MofNCompleteColumn(),
        "•",
        TimeRemainingColumn(),
    ]
    
    if show_speed:
        columns.insert(-1, TextColumn("[bold green]{task.speed} items/sec"))
        columns.insert(-1, "•")
    
    return Progress(
        *columns,
        console=_console,
        refresh_per_second=10,
        expand=True
    )


def create_header(title: str, subtitle: str = "") -> Panel:
    """Create a beautiful header panel."""
    header_text = Text(title, style="bold cyan", justify="center")
    if subtitle:
        header_text.append(f"\n{subtitle}", style="dim")
    
    return Panel(
        Align.center(header_text),
        border_style="bright_blue",
        padding=(1, 2)
    )


def create_summary_table(stats: dict) -> Table:
    """Create a summary table for statistics."""
    table = Table(title="📊 Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    for key, value in stats.items():
        table.add_row(key, str(value))
    
    return table


def print_success(message: str, details: Optional[str] = None) -> None:
    """Print success message with optional details."""
    text = f"[bold green]✅ {message}[/bold green]"
    if details:
        text += f"\n[dim green]{details}[/dim green]"
    _console.print(text)


def print_error(message: str, details: Optional[str] = None) -> None:
    """Print error message with optional details."""
    text = f"[bold red]❌ {message}[/bold red]"
    if details:
        text += f"\n[dim red]{details}[/dim red]"
    _console.print(text)


def print_warning(message: str, details: Optional[str] = None) -> None:
    """Print warning message with optional details."""
    text = f"[bold yellow]⚠️  {message}[/bold yellow]"
    if details:
        text += f"\n[dim yellow]{details}[/dim yellow]"
    _console.print(text)


def print_info(message: str, details: Optional[str] = None) -> None:
    """Print info message with optional details."""
    text = f"[bold cyan]ℹ️  {message}[/bold cyan]"
    if details:
        text += f"\n[dim cyan]{details}[/dim cyan]"
    _console.print(text)


def print_step(step_num: int, total_steps: int, message: str) -> None:
    """Print a numbered step."""
    _console.print(f"[bold blue]Step {step_num}/{total_steps}:[/bold blue] [white]{message}[/white]")


def log_message(message: str, level: str = "info") -> None:
    """Log message without interfering with progress bars."""
    timestamp = time.strftime("%H:%M:%S")
    
    level_styles = {
        "info": "cyan",
        "warning": "yellow", 
        "error": "red",
        "success": "green"
    }
    
    style = level_styles.get(level, "white")
    _console.log(f"[{style}]{message}[/{style}]", _stack_offset=2)


def print_banner(text: str, style: str = "bold cyan") -> None:
    """Print a banner message."""
    _console.rule(f"[{style}]{text}[/{style}]", style="bright_blue")


def create_status_panel(title: str, content: str, style: str = "green") -> Panel:
    """Create a status panel."""
    return Panel(
        content,
        title=title,
        border_style=style,
        padding=(0, 1)
    )
