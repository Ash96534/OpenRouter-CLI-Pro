# OpenRouter CLI Pro

Advanced command-line interface alternative to Claude Code with automatic tool awareness. The AI automatically detects your filesystem, suggests operations (like /write, /run, /file), recognizes project types (Python, Node, Rust), and supports over 100+ models via OpenRouter.

**Tech stack:** Python, rich (for terminal UI), prompt_toolkit/pyreadline3, pyperclip (clipboard integration)

## Setup

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY="your-key-here"
python cli.py