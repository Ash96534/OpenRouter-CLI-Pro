#!/usr/bin/env python3
"""OpenRouter CLI Pro - AI-powered CLI alternative."""

import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

console = Console()


def detect_project_type(path="."):
    """Auto-detect project type based on files in directory."""
    indicators = {
        "Python": ["requirements.txt", "setup.py", "pyproject.toml", "main.py"],
        "Node.js": ["package.json", "index.js", "app.js"],
        "Rust": ["Cargo.toml", "main.rs"],
        "Go": ["go.mod", "main.go"],
    }
    for proj_type, files in indicators.items():
        for f in files:
            if os.path.exists(os.path.join(path, f)):
                return proj_type
    return "Unknown"


def main():
    console.print(Panel.fit("OpenRouter CLI Pro", style="bold blue"))
    console.print(f"Project type: [green]{detect_project_type()}[/green]")
    console.print("Type your request or '/help' for commands.\n")

    session = PromptSession(history=InMemoryHistory())

    while True:
        try:
            user_input = session.prompt("> ")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("/quit", "/exit", "q"):
            break
        if user_input.lower() == "/help":
            console.print(
                Markdown(
                """
# Commands
- `/write <file> <content>` - Write to a file
- `/run <command>` - Run a shell command
- `/file <path>` - Read a file
- `/project` - Show detected project type
- `/quit` - Exit
"""
                )
            )
            continue

        console.print(f"\n[bold yellow]Processing:[/bold yellow] {user_input}\n")
        # Placeholder for OpenRouter API call
        console.print("[dim]AI response placeholder - integrate OpenRouter API here[/dim]\n")


if __name__ == "__main__":
    main()
