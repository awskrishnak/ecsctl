import time
import click
from datetime import datetime, timezone


def watch_loop(fn, interval=2):
    """Run fn repeatedly, clearing screen between iterations."""
    try:
        while True:
            click.clear()
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            click.echo(f"Every {interval}s — {now}\n")
            fn()
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\nStopped.")
