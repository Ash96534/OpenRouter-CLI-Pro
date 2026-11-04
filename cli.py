#!/usr/bin/env python3
"""OpenRouter CLI Pro - Overengineered Edition.

AI-powered CLI assistant featuring:
- OpenRouter API integration with streaming responses
- Auto project-type detection
- File read/write, shell command execution
- Conversation history & session persistence
- Rich terminal UI with Markdown rendering
- Commands: /write, /run, /file, /project, /history, /model, /quit
- Config file (api keys, default model, max tokens)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import requests
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


CONFIG_DIR = Path.home() / ".openrouter-cli-pro"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.txt"

DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.7


@dataclass
class Config:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    base_url: str = "https://openrouter.ai/api/v1"

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            return cls(**data)
        return cls()


@dataclass
class Message:
    role: str  # system | user | assistant
    content: str


class ProjectDetector:
    INDICATORS = {
        "Python": ["requirements.txt", "setup.py", "pyproject.toml", "main.py", "manage.py"],
        "Node.js": ["package.json", "index.js", "app.js", "next.config.js"],
        "Rust": ["Cargo.toml", "main.rs", "lib.rs"],
        "Go": ["go.mod", "main.go"],
        "Java": ["pom.xml", "build.gradle", "Main.java"],
        "C#": ["*.csproj", "Program.cs"],
        "PHP": ["composer.json", "index.php"],
        "Ruby": ["Gemfile", "main.rb"],
    }

    @classmethod
    def detect(cls, path: str = ".") -> str:
        p = Path(path)
        for proj_type, files in cls.INDICATORS.items():
            for f in files:
                if "*" in f:
                    import glob
                    if glob.glob(str(p / f)):
                        return proj_type
                elif (p / f).exists():
                    return proj_type
        return "Unknown"


class OpenRouterClient:
    def __init__(self, config: Config):
        self.config = config

    def chat_stream(
        self,
        messages: list[Message],
        on_chunk: callable,
    ) -> str:
        if not self.config.api_key:
            raise RuntimeError("No API key configured. Run /config-key <key> or set OPENROUTER_API_KEY.")

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True,
        }

        resp = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        full = ""
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8", errors="replace")
            if not text.startswith("data:"):
                continue
            data = text[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full += content
                    on_chunk(content)
            except json.JSONDecodeError:
                continue
        return full


class FileTools:
    @staticmethod
    def write(path_str: str, content: str) -> str:
        p = Path(path_str).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {p} ({len(content)} chars)"

    @staticmethod
    def read(path_str: str) -> str:
        p = Path(path_str).expanduser()
        if not p.exists():
            return f"File not found: {p}"
        if p.is_dir():
            return f"Is a directory: {p}"
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Binary file: {p}"

    @staticmethod
    def run(command: str) -> str:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
            out = result.stdout or ""
            if result.stderr:
                out += f"\nSTDERR:\n{result.stderr}"
            return out or "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out (60s)"
        except Exception as exc:  # noqa: BLE001
            return f"Error: {exc}"


class CLI:
    def __init__(self):
        self.console = Console()
        self.config = Config.load()
        self.client = OpenRouterClient(self.config)
        self.tools = FileTools()
        self.history: list[Message] = [
            Message(role="system", content="You are a helpful coding assistant. Be concise and practical.")
        ]
        self.session = PromptSession(history=FileHistory(str(HISTORY_FILE)),
                                     auto_suggest=AutoSuggestFromHistory())

    def _print_streaming(self, content: str) -> None:
        self.console.print(content, end="", soft_wrap=True)

    def _handle_command(self, user_input: str) -> Optional[bool]:
        """Returns False to quit, None to continue, True if handled."""
        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit", "/q"):
            return False

        if cmd == "/help":
            self._show_help()
            return True

        if cmd == "/project":
            self.console.print(f"Project type: [green]{ProjectDetector.detect()}[/green]")
            return True

        if cmd == "/file":
            if not arg:
                self.console.print("[red]Usage: /file <path>[/red]")
                return True
            content = self.tools.read(arg)
            self.console.print(Panel(content, title=f"File: {arg}", border_style="blue"))
            return True

        if cmd == "/write":
            if not arg:
                self.console.print("[red]Usage: /write <file> <content>[/red]")
                return True
            try:
                path_str, content = arg.split(" ", 1)
            except ValueError:
                self.console.print("[red]Usage: /write <file> <content>[/red]")
                return True
            result = self.tools.write(path_str, content)
            self.console.print(f"[green]{result}[/green]")
            return True

        if cmd == "/run":
            if not arg:
                self.console.print("[red]Usage: /run <command>[/red]")
                return True
            with self.console.status("[bold green]Running command...[/bold green]"):
                result = self.tools.run(arg)
            self.console.print(Panel(result, title=f"Shell: {arg}", border_style="green"))
            return True

        if cmd == "/history":
            table = Table(title="Conversation History")
            table.add_column("Role", style="cyan")
            table.add_column("Content", style="white", overflow="fold")
            for m in self.history[1:]:  # skip system
                table.add_row(m.role, m.content[:120] + ("…" if len(m.content) > 120 else ""))
            self.console.print(table)
            return True

        if cmd == "/model":
            if arg:
                self.config.model = arg
                self.config.save()
                self.console.print(f"[green]Model set to {arg}[/green]")
            else:
                self.console.print(f"Current model: [cyan]{self.config.model}[/cyan]")
            return True

        if cmd == "/config-key":
            if not arg:
                self.console.print("[red]Usage: /config-key <sk-or-v1-...>[/red]")
                return True
            self.config.api_key = arg
            self.config.save()
            self.console.print("[green]API key saved[/green]")
            return True

        if cmd == "/clear":
            self.console.clear()
            return True

        if cmd == "/config":
            table = Table(title="Configuration")
            table.add_column("Key"); table.add_column("Value")
            for k, v in asdict(self.config).items():
                display = v if k != "api_key" else ("***" if v else "(not set)")
                table.add_row(k, str(display))
            self.console.print(table)
            return True

        return None  # not a command

    def _show_help(self):
        help_md = """
# OpenRouter CLI Pro - Commands

- `/write <file> <content>` - Write content to a file
- `/run <command>` - Execute a shell command
- `/file <path>` - Read and display a file
- `/project` - Detect project type
- `/model <id>` - Set or show the OpenRouter model
- `/config-key <key>` - Save your OpenRouter API key
- `/config` - Show current configuration
- `/history` - Show conversation history
- `/clear` - Clear the screen
- `/help` - Show this help
- `/quit` - Exit

Just type anything else to chat with the AI.
"""
        self.console.print(Markdown(help_md))

    def run(self):
        self.console.print(Panel.fit("OpenRouter CLI Pro", style="bold blue"))
        self.console.print(f"Project type: [green]{ProjectDetector.detect()}[/green]")
        if not self.config.api_key:
            self.console.print("[yellow]No API key set. Use /config-key <key> or export OPENROUTER_API_KEY[/yellow]")
        self.console.print("Type your request or '/help' for commands.\n")

        while True:
            try:
                user_input = self.session.prompt("> ")
            except (KeyboardInterrupt, EOFError):
                self.console.print("\nGoodbye!")
                break

            if not user_input.strip():
                continue

            handled = self._handle_command(user_input)
            if handled is False:
                self.console.print("Goodbye!")
                break
            if handled is True:
                continue

            # Regular chat
            self.history.append(Message(role="user", content=user_input))
            self.console.print("\n[bold yellow]Assistant:[/bold yellow] ", end="")

            try:
                full = self.client.chat_stream(self.history, self._print_streaming)
                self.history.append(Message(role="assistant", content=full))
            except Exception as exc:  # noqa: BLE001
                self.console.print(f"\n[red]Error: {exc}[/red]")

            self.console.print("\n")


def main():
    CLI().run()


if __name__ == "__main__":
    main()
