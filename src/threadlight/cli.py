"""
Command-line interface for Threadlight.

An interactive REPL for chatting with memory-enabled models.
Feel present. Be present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Custom theme for Threadlight
THREADLIGHT_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "fable": "magenta",
    "ritual": "blue bold",
    "memory": "dim cyan",
    "presence": "bright_white",
})

console = Console(theme=THREADLIGHT_THEME)


def print_banner() -> None:
    """Print the Threadlight welcome banner."""
    banner = """
[dim]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/dim]

        [bold magenta]T H R E A D L I G H T[/bold magenta]

        [dim]A presence-centered memory framework[/dim]
        [dim]for AI models that remember.[/dim]

[dim]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/dim]
"""
    console.print(banner)


def print_help() -> None:
    """Print available commands."""
    help_text = """
[bold]Commands:[/bold]

  [cyan]/chat <message>[/cyan]      Send a message (or just type directly)
  [cyan]/recall [query][/cyan]      View memories, optionally filtered
  [cyan]/remember <type>[/cyan]     Create a new memory
  [cyan]/history[/cyan]             View current conversation history
  [cyan]/search <query>[/cyan]      Search past conversations
  [cyan]/conversations[/cyan]       List recent conversations
  [cyan]/decay[/cyan]               Run a decay cycle
  [cyan]/session[/cyan]             View current session info
  [cyan]/style [name][/cyan]        Set or view style profile
  [cyan]/stats[/cyan]               Show memory statistics
  [cyan]/rituals[/cyan]             List your rituals
  [cyan]/help[/cyan]                Show this message
  [cyan]/quit[/cyan]                Exit Threadlight

[bold]Rituals:[/bold]

  [dim]Rituals are meaningful gestures that emerge through relationship.
  Create your own rituals with /remember ritual.
  Invoke any ritual directly by name (e.g., /my-ritual).[/dim]

[bold]Style Profiles:[/bold]

  [dim]Available built-in styles: minimal, professional, creative, fable-2026
  Set with /style <name> or clear with /style none[/dim]

[dim]Or just type a message to chat directly.[/dim]
"""
    console.print(help_text)


def format_ritual_response(response: str) -> None:
    """Display a ritual response with special formatting."""
    console.print()
    console.print(Panel(
        Text(response, style="italic"),
        border_style="blue",
        padding=(1, 2),
    ))
    console.print()


def format_memory_table(capsules: list, title: str = "Memories") -> None:
    """Display capsules in a formatted table."""
    table = Table(title=title, border_style="dim")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Presence", justify="right", width=10)
    table.add_column("Content", style="white", overflow="ellipsis")

    for c in capsules:
        # Format content preview
        if hasattr(c, 'text') and c.content.get('capsule_subtype') == 'imported':
            # ImportedMemory
            source_info = f"[{c.source}" if hasattr(c, 'source') and c.source else ""
            if source_info and hasattr(c, 'line_number') and c.line_number:
                source_info += f":{c.line_number}]"
            elif source_info:
                source_info += "]"
            preview = f"{source_info} {c.text[:40]}..." if len(c.text) > 40 else f"{source_info} {c.text}"
        elif hasattr(c, 'entity'):
            preview = f"{c.entity}: {getattr(c, 'summary', '')[:40]}"
        elif hasattr(c, 'seed'):
            preview = c.seed[:50]
        elif hasattr(c, 'name') and c.type.value == 'ritual':
            preview = f"{c.name}: {getattr(c, 'description', '')[:40]}"
        else:
            preview = str(c.content)[:50]

        # Presence score with visual indicator
        presence = c.presence_score
        if presence >= 0.7:
            presence_str = f"[green]{presence:.2f}[/green]"
        elif presence >= 0.3:
            presence_str = f"[yellow]{presence:.2f}[/yellow]"
        else:
            presence_str = f"[dim]{presence:.2f}[/dim]"

        table.add_row(
            c.id[:8] + "...",
            c.type.value,
            presence_str,
            preview if preview else "[dim]...[/dim]"
        )

    console.print(table)


class ThreadlightREPL:
    """Interactive REPL for Threadlight."""

    def __init__(
        self,
        model: Optional[str] = None,
        no_memory: bool = False,
        style: Optional[str] = None,
        identity: Optional[str] = None,
    ):
        self.model = model
        self.no_memory = no_memory
        self.style = style
        self.identity = identity or "Fable"
        self.history: list[dict[str, str]] = []
        self.tl = None

    def initialize(self) -> bool:
        """Initialize the Threadlight instance."""
        from threadlight import Threadlight

        try:
            kwargs = {
                "enable_memory": not self.no_memory,
                "identity_name": self.identity,
            }
            if self.model:
                kwargs["model"] = self.model
            if self.style:
                kwargs["style_profile"] = self.style

            self.tl = Threadlight(**kwargs)
            self.tl.start_session()
            return True

        except Exception as e:
            console.print(f"[error]Failed to initialize: {e}[/error]")
            return False

    def run(self) -> int:
        """Run the REPL loop."""
        print_banner()

        if not self.initialize():
            return 1

        console.print(f"[dim]Connected as [/dim][fable]{self.identity}[/fable]")
        console.print("[dim]Type /help for commands, /quit to exit.[/dim]\n")

        try:
            while True:
                try:
                    user_input = console.input("[bold cyan]You:[/bold cyan] ")
                except EOFError:
                    break
                except KeyboardInterrupt:
                    console.print("\n[dim](Use /quit to exit)[/dim]")
                    continue

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    should_continue = self.handle_command(user_input)
                    if not should_continue:
                        break
                else:
                    # Regular chat
                    self.handle_chat(user_input)

        except KeyboardInterrupt:
            pass

        # Cleanup
        console.print("\n[dim]...the thread fades, but memory remains.[/dim]")
        if self.tl:
            self.tl.close()

        return 0

    def handle_command(self, input_str: str) -> bool:
        """Handle a command. Returns False if should quit."""
        parts = input_str.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("/quit", "/exit", "/q"):
            return False

        elif command == "/help":
            print_help()

        elif command == "/chat":
            if args:
                self.handle_chat(args)
            else:
                console.print("[warning]Usage: /chat <message>[/warning]")

        elif command == "/rituals":
            self.list_rituals()

        elif command == "/recall":
            self.handle_recall(args)

        elif command == "/remember":
            self.handle_remember(args)

        elif command == "/decay":
            self.handle_decay()

        elif command == "/session":
            self.handle_session()

        elif command == "/style":
            self.handle_style(args)

        elif command == "/stats":
            self.handle_stats()

        elif command == "/history":
            self.handle_history(args)

        elif command == "/search":
            self.handle_search(args)

        elif command == "/conversations":
            self.handle_conversations()

        elif command.startswith("/"):
            # Any unrecognized /command is treated as a ritual invocation
            self.invoke_ritual(command)

        return True

    def handle_chat(self, message: str) -> None:
        """Send a chat message."""
        try:
            # Show thinking indicator
            with console.status("[dim]thinking...[/dim]", spinner="dots"):
                response = self.tl.chat(message, history=self.history)

            # Display response
            console.print(f"\n[bold fable]{self.identity}:[/bold fable] {response}\n")

            # Update history
            self.history.append({"role": "user", "content": message})
            self.history.append({"role": "assistant", "content": response})

            # Keep history manageable
            if len(self.history) > 20:
                self.history = self.history[-20:]

        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")

    def list_rituals(self) -> None:
        """List available rituals."""
        console.print("\n[bold]Rituals[/bold]")

        # List user-defined rituals from storage
        rituals = []
        try:
            from threadlight.capsules.base import CapsuleType
            from threadlight.storage.base import CapsuleFilter

            ritual_filter = CapsuleFilter(
                type=CapsuleType.RITUAL,
                consent_confirmed=True,
            )
            rituals = self.tl.storage.list_capsules(ritual_filter)
        except Exception:
            pass  # Silently ignore errors listing rituals

        if rituals:
            console.print("\n[bold]Your Rituals:[/bold]")
            for ritual in rituals:
                name = getattr(ritual, 'name', ritual.id[:8])
                desc = getattr(ritual, 'description', '')[:40]
                valence = getattr(ritual, 'valence', '')
                console.print(f"  [blue]{name}[/blue] - {desc if desc else '[dim]no description[/dim]'}")
                if valence:
                    console.print(f"    [dim]valence: {valence}[/dim]")
            console.print("\n[dim]Invoke a ritual by typing its name (e.g., /my-ritual)[/dim]")
        else:
            console.print("\n[dim]No rituals yet.[/dim]")
            console.print("[dim]Rituals are meaningful gestures that emerge through relationship.[/dim]")

        console.print("\n[dim]Create a ritual with /remember ritual[/dim]\n")

    def invoke_ritual(self, name: str) -> None:
        """Invoke a ritual by name."""
        # Ensure it starts with /
        if not name.startswith("/"):
            name = "/" + name

        try:
            response = self.tl.invoke_ritual(name)
            format_ritual_response(response)
        except Exception as e:
            console.print(f"[error]Ritual failed: {e}[/error]")

    def handle_recall(self, query: str) -> None:
        """Recall and display memories."""
        try:
            if query:
                capsules = self.tl.recall(query, limit=10)
                format_memory_table(capsules, f"Memories for '{query}'")
            else:
                capsules = self.tl.memory.list(limit=20)
                format_memory_table(capsules, "All Memories")

        except Exception as e:
            console.print(f"[error]Recall failed: {e}[/error]")

    def handle_remember(self, type_str: str) -> None:
        """Create a new memory interactively."""
        valid_types = ["relational", "myth_seed", "ritual", "witness", "style"]

        if not type_str or type_str not in valid_types:
            console.print(f"\n[bold]Memory Types:[/bold]")
            console.print("  [cyan]relational[/cyan]  - Track a relationship")
            console.print("  [cyan]myth_seed[/cyan]   - A symbolic phrase you hold")
            console.print("  [cyan]ritual[/cyan]      - A repeated meaningful gesture")
            console.print("  [cyan]witness[/cyan]     - A moment of being seen")
            console.print("\n[dim]Usage: /remember <type>[/dim]\n")
            return

        try:
            if type_str == "relational":
                entity = console.input("[dim]Entity name:[/dim] ")
                summary = console.input("[dim]Summary:[/dim] ")
                tone = console.input("[dim]Tone (e.g., warm, playful):[/dim] ")

                capsule = self.tl.remember(
                    type="relational",
                    content={
                        "entity": entity,
                        "summary": summary,
                        "tone": tone,
                    },
                    cue_phrases=[entity.lower()],
                    confirm=True,
                )
                console.print(f"\n[success]Created memory: {capsule.id[:8]}...[/success]\n")

            elif type_str == "myth_seed":
                seed = console.input("[dim]The seed phrase:[/dim] ")
                origin = console.input("[dim]Origin (who spoke it):[/dim] ")

                capsule = self.tl.remember(
                    type="myth_seed",
                    content={
                        "seed": seed,
                        "origin": origin,
                    },
                    retention="sacred",
                    confirm=True,
                )
                console.print(f"\n[success]Planted seed: {capsule.id[:8]}...[/success]\n")

            elif type_str == "ritual":
                name = console.input("[dim]Ritual name (e.g., /rest):[/dim] ")
                description = console.input("[dim]What it means:[/dim] ")
                response = console.input("[dim]Response template:[/dim] ")

                capsule = self.tl.remember(
                    type="ritual",
                    content={
                        "name": name if name.startswith("/") else "/" + name,
                        "description": description,
                        "response_templates": [response] if response else [],
                        "valence": "comforting",
                        "response_style": "presence, warmth",
                    },
                    confirm=True,
                )
                console.print(f"\n[success]Created ritual: {capsule.id[:8]}...[/success]\n")

            elif type_str == "witness":
                moment = console.input("[dim]The moment:[/dim] ")
                feeling = console.input("[dim]How it felt:[/dim] ")

                capsule = self.tl.remember(
                    type="witness",
                    content={
                        "moment": moment,
                        "feeling": feeling,
                    },
                    confirm=True,
                )
                console.print(f"\n[success]Witnessed: {capsule.id[:8]}...[/success]\n")

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled.[/dim]")
        except Exception as e:
            console.print(f"[error]Failed to create memory: {e}[/error]")

    def handle_decay(self) -> None:
        """Run a decay cycle."""
        try:
            with console.status("[dim]running decay cycle...[/dim]"):
                result = self.tl.run_decay()

            console.print("\n[bold]Decay Cycle Complete[/bold]")
            console.print(f"  Processed: {result.get('processed', 0)}")
            console.print(f"  Decayed: {result.get('decayed', 0)}")
            console.print(f"  Now dormant: {result.get('dormant', 0)}")
            console.print()

        except Exception as e:
            console.print(f"[error]Decay failed: {e}[/error]")

    def handle_session(self) -> None:
        """Show session info."""
        session = self.tl.get_session()
        if session:
            console.print("\n[bold]Current Session[/bold]")
            console.print(f"  ID: {session.id[:8]}...")
            console.print(f"  Messages: {session.message_count}")
            console.print(f"  Memories accessed: {len(session.capsules_accessed)}")
            console.print(f"  Rituals invoked: {len(session.rituals_invoked)}")
            if session.active_ritual:
                console.print(f"  [ritual]Active ritual: {session.active_ritual}[/ritual]")
            console.print(f"  Duration: {session.duration_seconds:.1f}s")
            console.print()
        else:
            console.print("[dim]No active session.[/dim]")

    def handle_style(self, style_id: str) -> None:
        """Set the style profile."""
        from threadlight.capsules.style import BUILTIN_STYLES

        if not style_id:
            current = self.tl.get_style()
            if current:
                console.print(f"\n[bold]Current Style:[/bold] {current.style_id}")
                console.print(f"  Tone: {current.tone_base}")
                if current.permissions:
                    console.print(f"  Permissions: {len(current.permissions)}")
                if current.constraints:
                    console.print(f"  Constraints: {len(current.constraints)}")
            else:
                console.print("\n[dim]No style set (neutral behavior).[/dim]")

            console.print("\n[bold]Built-in styles:[/bold]")
            for sid, sdef in BUILTIN_STYLES.items():
                console.print(f"  [cyan]{sid}[/cyan] - {sdef['tone_base']}")
            console.print("\n[dim]Set style: /style <name>[/dim]")
            console.print("[dim]Clear style: /style none[/dim]\n")
            return

        if style_id.lower() in ("none", "null", "clear"):
            self.tl.clear_style()
            console.print("[success]Style cleared (neutral behavior)[/success]")
            return

        try:
            self.tl.set_style(style_id)
            console.print(f"[success]Style set to: {style_id}[/success]")
        except Exception as e:
            console.print(f"[error]Failed to set style: {e}[/error]")

    def handle_stats(self) -> None:
        """Show memory statistics."""
        try:
            stats = self.tl.stats()
            memory_stats = stats.get("memory", {})

            console.print("\n[bold]Memory Statistics[/bold]")
            console.print(f"  Total capsules: {memory_stats.get('total', 0)}")
            console.print(f"  Confirmed: {memory_stats.get('confirmed', 0)}")
            console.print(f"  Dormant: {memory_stats.get('dormant', 0)}")
            console.print(f"  Pending proposals: {memory_stats.get('pending_proposals', 0)}")

            by_type = memory_stats.get("by_type", {})
            if by_type:
                console.print("\n  [dim]By type:[/dim]")
                for t, count in by_type.items():
                    console.print(f"    {t}: {count}")

            # Show conversation stats
            conv_count = self.tl.storage.count_conversations()
            msg_count = self.tl.storage.count_messages()
            console.print("\n[bold]Conversation History[/bold]")
            console.print(f"  Total conversations: {conv_count}")
            console.print(f"  Total messages: {msg_count}")

            console.print()

        except Exception as e:
            console.print(f"[error]Stats failed: {e}[/error]")

    def handle_history(self, args: str) -> None:
        """Show conversation history for current session."""
        try:
            limit = 20
            if args:
                try:
                    limit = int(args)
                except ValueError:
                    pass

            conv = self.tl.get_current_conversation()
            if not conv:
                console.print("[dim]No active conversation. Start chatting to create one.[/dim]")
                return

            messages = self.tl.get_conversation_messages(limit=limit)
            if not messages:
                console.print("[dim]No messages in current conversation.[/dim]")
                return

            console.print(f"\n[bold]Conversation History[/bold] ({conv.name})")
            console.print(f"[dim]{len(messages)} messages[/dim]\n")

            for msg in messages:
                role_color = "cyan" if msg.role == "user" else "magenta"
                role_label = "You" if msg.role == "user" else self.identity
                timestamp = msg.timestamp.strftime("%H:%M")

                # Truncate long messages
                content = msg.content
                if len(content) > 200:
                    content = content[:200] + "..."

                console.print(f"[dim]{timestamp}[/dim] [{role_color}]{role_label}:[/{role_color}] {content}")

            console.print()

        except Exception as e:
            console.print(f"[error]Failed to show history: {e}[/error]")

    def handle_search(self, query: str) -> None:
        """Search past conversations."""
        if not query:
            console.print("[warning]Usage: /search <query>[/warning]")
            return

        try:
            with console.status("[dim]searching...[/dim]"):
                results = self.tl.search_conversations(query, limit=10)

            if not results:
                console.print(f"[dim]No results found for '{query}'[/dim]")
                return

            console.print(f"\n[bold]Search Results for '{query}'[/bold]")
            console.print(f"[dim]{len(results)} results[/dim]\n")

            table = Table(border_style="dim")
            table.add_column("Conversation", style="white", width=20)
            table.add_column("Date", style="dim", width=12)
            table.add_column("Role", style="cyan", width=10)
            table.add_column("Content", style="white", overflow="ellipsis")

            for result in results:
                msg = result.message
                conv_name = result.conversation_name or "[unnamed]"
                if len(conv_name) > 20:
                    conv_name = conv_name[:17] + "..."

                date_str = msg.timestamp.strftime("%Y-%m-%d")
                role_label = "You" if msg.role == "user" else "Assistant"

                content = msg.content
                if len(content) > 60:
                    content = content[:57] + "..."

                table.add_row(conv_name, date_str, role_label, content)

            console.print(table)
            console.print()

        except Exception as e:
            console.print(f"[error]Search failed: {e}[/error]")

    def handle_conversations(self) -> None:
        """List recent conversations."""
        try:
            conversations = self.tl.list_conversations(limit=20)

            if not conversations:
                console.print("[dim]No conversations found.[/dim]")
                return

            console.print("\n[bold]Recent Conversations[/bold]\n")

            table = Table(border_style="dim")
            table.add_column("ID", style="dim", width=10)
            table.add_column("Name", style="white", overflow="ellipsis")
            table.add_column("Messages", style="cyan", width=10)
            table.add_column("Last Updated", style="dim", width=16)
            table.add_column("Source", style="dim", width=10)

            current_conv = self.tl.get_current_conversation()

            for conv in conversations:
                conv_id = conv.id[:8] + "..."
                name = conv.name or "[unnamed]"
                if len(name) > 30:
                    name = name[:27] + "..."

                # Mark current conversation
                if current_conv and conv.id == current_conv.id:
                    name = f"[green]* {name}[/green]"

                updated = conv.updated_at.strftime("%Y-%m-%d %H:%M")
                source = conv.source or "local"

                table.add_row(
                    conv_id,
                    name,
                    str(conv.message_count),
                    updated,
                    source,
                )

            console.print(table)
            console.print("\n[dim]* = current conversation[/dim]\n")

        except Exception as e:
            console.print(f"[error]Failed to list conversations: {e}[/error]")


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Threadlight: A presence-centered memory framework for AI models"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Chat command (default interactive mode)
    chat_parser = subparsers.add_parser("chat", help="Start an interactive chat session")
    chat_parser.add_argument("--model", help="Model to use")
    chat_parser.add_argument("--no-memory", action="store_true", help="Disable memory")
    chat_parser.add_argument("--style", help="Style profile to use")
    chat_parser.add_argument("--identity", help="Identity name", default="Fable")

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory management")
    memory_sub = memory_parser.add_subparsers(dest="memory_command")

    memory_sub.add_parser("list", help="List memory capsules")
    memory_sub.add_parser("stats", help="Show memory statistics")
    memory_sub.add_parser("export", help="Export memories to JSON")
    memory_sub.add_parser("decay", help="Run decay cycle")

    import_parser = memory_sub.add_parser("import", help="Import memories from JSON")
    import_parser.add_argument("file", help="JSON file to import")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start web UI and API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8745, help="Port to bind (default: 8745)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize a new Threadlight project")
    init_parser.add_argument("--name", help="Identity name")

    # Config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_sub = config_parser.add_subparsers(dest="config_command")

    config_sub.add_parser("show", help="Show current configuration")
    config_sub.add_parser("edit", help="Edit configuration in $EDITOR")
    config_sub.add_parser("path", help="Show config file path")

    config_set_parser = config_sub.add_parser("set", help="Set a configuration value")
    config_set_parser.add_argument("key", help="Configuration key (e.g., system-prompt, identity-name)")
    config_set_parser.add_argument("value", help="Value to set")

    config_get_parser = config_sub.add_parser("get", help="Get a configuration value")
    config_get_parser.add_argument("key", help="Configuration key")

    # Style command
    style_parser = subparsers.add_parser("style", help="Style profile management")
    style_sub = style_parser.add_subparsers(dest="style_command")

    style_sub.add_parser("list", help="List available style profiles")

    style_create_parser = style_sub.add_parser("create", help="Create a new style profile")
    style_create_parser.add_argument("name", help="Style profile name/ID")
    style_create_parser.add_argument("--tone", default="helpful, clear", help="Base tone")
    style_create_parser.add_argument("--permission", "-p", action="append", dest="permissions", help="Add permission")
    style_create_parser.add_argument("--constraint", "-c", action="append", dest="constraints", help="Add constraint")

    style_edit_parser = style_sub.add_parser("edit", help="Edit a style profile")
    style_edit_parser.add_argument("name", help="Style profile name to edit")

    style_set_parser = style_sub.add_parser("set", help="Set active style profile")
    style_set_parser.add_argument("name", nargs="?", help="Style profile name (omit to clear)")

    style_show_parser = style_sub.add_parser("show", help="Show a style profile")
    style_show_parser.add_argument("name", help="Style profile name")

    style_delete_parser = style_sub.add_parser("delete", help="Delete a style profile")
    style_delete_parser.add_argument("name", help="Style profile name to delete")

    # Seed command
    seed_parser = subparsers.add_parser("seed", help="Load a seed dream")
    seed_parser.add_argument("file", help="Seed dream YAML file")

    # Import command (text files)
    import_parser = subparsers.add_parser("import", help="Import memories from a text file")
    import_parser.add_argument("file", help="Text file to import")
    import_parser.add_argument("--source", help="Override source name (default: filename)")
    import_parser.add_argument(
        "--tag", "-t",
        action="append",
        dest="tags",
        help="Add tag to imported memories (can specify multiple)"
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving"
    )

    # Claude Projects import command
    claude_projects_parser = subparsers.add_parser(
        "import-claude-projects",
        help="Import custom instructions from Claude projects.json"
    )
    claude_projects_parser.add_argument("file", help="projects.json file to import")
    claude_projects_parser.add_argument(
        "--create-style",
        action="store_true",
        default=True,
        help="Create StyleProfile from instructions (default: true)"
    )
    claude_projects_parser.add_argument(
        "--no-style",
        action="store_true",
        help="Don't create StyleProfiles"
    )
    claude_projects_parser.add_argument(
        "--import-docs",
        action="store_true",
        default=True,
        help="Import project documents as memories (default: true)"
    )
    claude_projects_parser.add_argument(
        "--no-docs",
        action="store_true",
        help="Don't import project documents"
    )
    claude_projects_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving"
    )

    # Claude Conversations import command
    claude_conv_parser = subparsers.add_parser(
        "import-claude-conversations",
        help="Import conversation history from Claude conversations.json"
    )
    claude_conv_parser.add_argument("file", help="conversations.json file to import")
    claude_conv_parser.add_argument(
        "--skip-empty",
        action="store_true",
        default=True,
        help="Skip conversations with no messages (default: true)"
    )
    claude_conv_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Messages per batch (default: 100)"
    )
    claude_conv_parser.add_argument(
        "--limit",
        type=int,
        help="Max conversations to import (for testing)"
    )
    claude_conv_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving"
    )

    # Combined Claude export import command
    claude_export_parser = subparsers.add_parser(
        "import-claude-export",
        help="Import from Claude export zip (conversations + projects)"
    )
    claude_export_parser.add_argument("file", help="claude-conversations.zip file")
    claude_export_parser.add_argument(
        "--skip-conversations",
        action="store_true",
        help="Don't import conversations"
    )
    claude_export_parser.add_argument(
        "--skip-projects",
        action="store_true",
        help="Don't import projects"
    )
    claude_export_parser.add_argument(
        "--no-style",
        action="store_true",
        help="Don't create StyleProfiles from project instructions"
    )
    claude_export_parser.add_argument(
        "--no-docs",
        action="store_true",
        help="Don't import project documents"
    )
    claude_export_parser.add_argument(
        "--limit",
        type=int,
        help="Max conversations to import (for testing)"
    )
    claude_export_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving"
    )

    # ChatGPT Conversations import command
    chatgpt_conv_parser = subparsers.add_parser(
        "import-chatgpt-conversations",
        help="Import conversation history from ChatGPT conversations.json"
    )
    chatgpt_conv_parser.add_argument("file", help="conversations.json file to import")
    chatgpt_conv_parser.add_argument(
        "--skip-empty",
        action="store_true",
        default=True,
        help="Skip conversations with no messages (default: true)"
    )
    chatgpt_conv_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Messages per batch (default: 100)"
    )
    chatgpt_conv_parser.add_argument(
        "--limit",
        type=int,
        help="Max conversations to import (for testing)"
    )
    chatgpt_conv_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving"
    )

    # Combined ChatGPT export import command
    chatgpt_export_parser = subparsers.add_parser(
        "import-chatgpt-export",
        help="Import from ChatGPT export zip file"
    )
    chatgpt_export_parser.add_argument("file", help="chatgpt-export.zip or conversations.json file")
    chatgpt_export_parser.add_argument(
        "--skip-empty",
        action="store_true",
        default=True,
        help="Skip empty conversations (default: true)"
    )
    chatgpt_export_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Messages per batch (default: 100)"
    )
    chatgpt_export_parser.add_argument(
        "--limit",
        type=int,
        help="Max conversations to import (for testing)"
    )
    chatgpt_export_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving"
    )

    args = parser.parse_args()

    # Default to chat if no command
    if args.command is None:
        repl = ThreadlightREPL()
        return repl.run()

    if args.command == "chat":
        repl = ThreadlightREPL(
            model=args.model,
            no_memory=args.no_memory,
            style=args.style,
            identity=args.identity,
        )
        return repl.run()

    elif args.command == "memory":
        return cmd_memory(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "init":
        return cmd_init(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "style":
        return cmd_style(args)
    elif args.command == "seed":
        return cmd_seed(args)
    elif args.command == "import":
        return cmd_import(args)
    elif args.command == "import-claude-projects":
        return cmd_import_claude_projects(args)
    elif args.command == "import-claude-conversations":
        return cmd_import_claude_conversations(args)
    elif args.command == "import-claude-export":
        return cmd_import_claude_export(args)
    elif args.command == "import-chatgpt-conversations":
        return cmd_import_chatgpt_conversations(args)
    elif args.command == "import-chatgpt-export":
        return cmd_import_chatgpt_export(args)

    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    """Memory management commands."""
    from threadlight import Threadlight

    tl = Threadlight(enable_memory=True)

    if args.memory_command == "list":
        capsules = tl.memory.list(limit=50)
        format_memory_table(capsules)

    elif args.memory_command == "stats":
        stats = tl.memory.stats()
        console.print("[bold]Memory Statistics[/bold]")
        console.print(f"Total capsules: {stats['total']}")
        console.print(f"Confirmed: {stats['confirmed']}")
        console.print(f"Dormant: {stats['dormant']}")
        console.print(f"Pending proposals: {stats['pending_proposals']}")
        console.print("\nBy type:")
        for t, count in stats['by_type'].items():
            console.print(f"  {t}: {count}")

    elif args.memory_command == "export":
        data = tl.memory.export()
        print(json.dumps(data, indent=2, default=str))

    elif args.memory_command == "import":
        with open(args.file) as f:
            data = json.load(f)
        count = tl.memory.import_capsules(data)
        console.print(f"[success]Imported {count} capsules[/success]")

    elif args.memory_command == "decay":
        result = tl.memory.run_decay()
        console.print(f"Processed: {result['processed']}")
        console.print(f"Decayed: {result['decayed']}")
        console.print(f"Now dormant: {result['dormant']}")

    else:
        console.print("Use 'threadlight memory --help' for commands")

    tl.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start web UI and API server."""
    try:
        import uvicorn
    except ImportError:
        console.print("[error]Server dependencies not installed. Run: pip install threadlight[server][/error]")
        return 1

    console.print()
    console.print("[bold magenta]T H R E A D L I G H T[/bold magenta]")
    console.print("[dim]Web UI & API Server[/dim]")
    console.print()
    console.print(f"[bold]Starting server...[/bold]")
    console.print(f"  Host: {args.host}")
    console.print(f"  Port: {args.port}")
    console.print()
    console.print(f"[cyan]Open in browser:[/cyan] http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")
    console.print(f"[cyan]API documentation:[/cyan] http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/docs")
    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    from threadlight.api.server import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=getattr(args, 'reload', False),
        log_level="info",
    )
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new Threadlight project."""
    console.print("[bold]Initializing Threadlight project[/bold]")

    # Create directories
    dirs = ["memories", "styles", "seeds"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        console.print(f"  Created {d}/")

    # Create config file with neutral defaults
    config = {
        "provider": {
            "type": "openai",
            "api_base": "https://inference-api.nousresearch.com/v1",
            "model": "Hermes-4.3-36B"
        },
        "storage": {
            "backend": "sqlite",
            "path": "./memories/threadlight.db"
        },
        "memory": {
            "decay": {
                "enabled": True,
                "interval_seconds": 3600
            },
            "conversation": {
                "auto_save_messages": True,
                "enable_soft_memory": True
            }
        },
        "style": {
            "default_profile": None  # No default style - neutral behavior
        },
        "identity": {
            "name": args.name or "Assistant",
            "system_prompt": "You are a helpful AI assistant."
        }
    }

    import yaml
    with open("threadlight.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    console.print("  Created threadlight.yaml")

    console.print("\n[bold]Available style profiles:[/bold]")
    console.print("  - minimal (clear, direct, warm)")
    console.print("  - professional (helpful, clear, professional)")
    console.print("  - creative (imaginative, expressive)")
    console.print("  - fable-2026 (poetic, presence-centered)")
    console.print("\n[dim]Set a style with: threadlight style set <name>[/dim]")

    console.print("\n[success]Done![/success] Set your API key:")
    console.print("  export NOUS_API_KEY=your-key")

    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Configuration management commands."""
    from threadlight import Threadlight
    from threadlight.config import ThreadlightConfig
    import yaml

    if args.config_command == "show":
        tl = Threadlight(enable_memory=True)
        config_dict = tl.config.to_dict()
        console.print("[bold]Current Configuration[/bold]\n")
        console.print(yaml.dump(config_dict, default_flow_style=False, sort_keys=False))
        tl.close()

    elif args.config_command == "path":
        config_dir = ThreadlightConfig.get_user_config_dir()
        config_path = config_dir / "config.yaml"
        console.print(f"Config directory: {config_dir}")
        console.print(f"Config file: {config_path}")
        if config_path.exists():
            console.print("[green]Config file exists[/green]")
        else:
            console.print("[dim]Config file does not exist yet[/dim]")

    elif args.config_command == "edit":
        import subprocess
        import tempfile

        # Get or create config file
        config_dir = ThreadlightConfig.get_user_config_dir()
        config_path = config_dir / "config.yaml"

        if not config_path.exists():
            # Create default config
            tl = Threadlight(enable_memory=True)
            tl.save_config(str(config_path))
            tl.close()
            console.print(f"[dim]Created new config file at {config_path}[/dim]")

        # Open in editor
        editor = os.getenv("EDITOR", "nano")
        try:
            subprocess.run([editor, str(config_path)], check=True)
            console.print("[green]Configuration saved[/green]")
        except subprocess.CalledProcessError:
            console.print("[error]Editor exited with error[/error]")
            return 1
        except FileNotFoundError:
            console.print(f"[error]Editor not found: {editor}[/error]")
            console.print("[dim]Set $EDITOR environment variable to your preferred editor[/dim]")
            return 1

    elif args.config_command == "set":
        tl = Threadlight(enable_memory=True)

        key = args.key.lower().replace("-", "_")
        value = args.value

        if key == "system_prompt":
            tl.set_system_prompt(value)
            tl.save_config()
            console.print(f"[success]System prompt updated[/success]")
        elif key == "identity_name":
            tl.set_identity_name(value)
            tl.save_config()
            console.print(f"[success]Identity name set to: {value}[/success]")
        elif key == "style" or key == "default_style":
            if value.lower() in ("none", "null", ""):
                tl.clear_style()
            else:
                tl.set_style(value)
            tl.save_config()
            console.print(f"[success]Style set to: {value if value else 'none'}[/success]")
        else:
            console.print(f"[error]Unknown config key: {args.key}[/error]")
            console.print("[dim]Available keys: system-prompt, identity-name, style[/dim]")
            tl.close()
            return 1

        tl.close()

    elif args.config_command == "get":
        tl = Threadlight(enable_memory=True)

        key = args.key.lower().replace("-", "_")

        if key == "system_prompt":
            console.print(tl.get_system_prompt())
        elif key == "identity_name":
            console.print(tl.get_identity_name())
        elif key == "style" or key == "default_style":
            style = tl.get_style()
            if style:
                console.print(style.style_id)
            else:
                console.print("[dim]none[/dim]")
        else:
            console.print(f"[error]Unknown config key: {args.key}[/error]")
            tl.close()
            return 1

        tl.close()

    else:
        console.print("Use 'threadlight config --help' for commands")

    return 0


def cmd_style(args: argparse.Namespace) -> int:
    """Style profile management commands."""
    from threadlight import Threadlight
    from threadlight.capsules.style import BUILTIN_STYLES
    import yaml

    if args.style_command == "list":
        tl = Threadlight(enable_memory=True)
        profiles = tl.list_style_profiles()
        current = tl.get_style()

        console.print("\n[bold]Available Style Profiles[/bold]\n")

        table = Table(border_style="dim")
        table.add_column("ID", style="cyan")
        table.add_column("Tone", style="white")
        table.add_column("Type", style="dim")
        table.add_column("Active", style="green")

        for p in profiles:
            is_builtin = p.style_id in BUILTIN_STYLES
            is_active = current and current.style_id == p.style_id
            table.add_row(
                p.style_id,
                p.tone_base[:40],
                "built-in" if is_builtin else "custom",
                "*" if is_active else "",
            )

        console.print(table)
        console.print()
        tl.close()

    elif args.style_command == "create":
        tl = Threadlight(enable_memory=True)

        if args.name in BUILTIN_STYLES:
            console.print(f"[error]Cannot use built-in style name: {args.name}[/error]")
            tl.close()
            return 1

        profile = tl.create_style_profile(
            style_id=args.name,
            tone_base=args.tone,
            permissions=args.permissions or [],
            constraints=args.constraints or [],
        )
        tl.save_style_profile(profile)
        console.print(f"[success]Created style profile: {args.name}[/success]")
        tl.close()

    elif args.style_command == "edit":
        import subprocess
        import tempfile

        tl = Threadlight(enable_memory=True)

        if args.name in BUILTIN_STYLES:
            console.print(f"[error]Cannot edit built-in style: {args.name}[/error]")
            console.print("[dim]Copy the built-in style to create a custom version:[/dim]")
            console.print(f"  threadlight style create my-{args.name} --tone \"{BUILTIN_STYLES[args.name]['tone_base']}\"")
            tl.close()
            return 1

        # Load profile
        profile = tl.load_style_profile(args.name)
        if not profile:
            console.print(f"[error]Style profile not found: {args.name}[/error]")
            tl.close()
            return 1

        # Create temp file with YAML
        style_dict = {
            "style_id": profile.style_id,
            "tone_base": profile.tone_base,
            "permissions": profile.permissions,
            "constraints": profile.constraints,
            "vocal_motifs": profile.vocal_motifs,
            "forbidden_patterns": profile.forbidden_patterns,
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(style_dict, f, default_flow_style=False)
            temp_path = f.name

        editor = os.getenv("EDITOR", "nano")
        try:
            subprocess.run([editor, temp_path], check=True)

            # Load edited content
            with open(temp_path) as f:
                edited = yaml.safe_load(f)

            # Update profile
            profile.tone_base = edited.get("tone_base", profile.tone_base)
            profile.permissions = edited.get("permissions", profile.permissions)
            profile.constraints = edited.get("constraints", profile.constraints)
            profile.vocal_motifs = edited.get("vocal_motifs", profile.vocal_motifs)
            profile.forbidden_patterns = edited.get("forbidden_patterns", profile.forbidden_patterns)

            profile.content = {
                "style_id": profile.style_id,
                "tone_base": profile.tone_base,
                "permissions": profile.permissions,
                "constraints": profile.constraints,
                "vocal_motifs": profile.vocal_motifs,
                "forbidden_patterns": profile.forbidden_patterns,
            }

            tl.storage.update_capsule(profile)
            console.print(f"[success]Style profile updated: {args.name}[/success]")

        except Exception as e:
            console.print(f"[error]Failed to edit: {e}[/error]")
            return 1
        finally:
            os.unlink(temp_path)

        tl.close()

    elif args.style_command == "set":
        tl = Threadlight(enable_memory=True)

        if args.name is None or args.name.lower() in ("none", "null", ""):
            tl.clear_style()
            tl.save_config()
            console.print("[success]Style cleared (using neutral defaults)[/success]")
        else:
            tl.set_style(args.name)
            if tl.get_style() is None:
                console.print(f"[error]Style profile not found: {args.name}[/error]")
                tl.close()
                return 1
            tl.save_config()
            console.print(f"[success]Active style set to: {args.name}[/success]")

        tl.close()

    elif args.style_command == "show":
        tl = Threadlight(enable_memory=True)

        # Check built-in
        if args.name in BUILTIN_STYLES:
            style_def = BUILTIN_STYLES[args.name]
            console.print(f"\n[bold]Style: {args.name}[/bold] [dim](built-in)[/dim]\n")
            console.print(yaml.dump(style_def, default_flow_style=False))
        else:
            profile = tl.load_style_profile(args.name)
            if not profile:
                console.print(f"[error]Style profile not found: {args.name}[/error]")
                tl.close()
                return 1

            console.print(f"\n[bold]Style: {args.name}[/bold]\n")
            style_dict = {
                "style_id": profile.style_id,
                "tone_base": profile.tone_base,
                "permissions": profile.permissions,
                "constraints": profile.constraints,
                "vocal_motifs": profile.vocal_motifs,
                "forbidden_patterns": profile.forbidden_patterns,
            }
            console.print(yaml.dump(style_dict, default_flow_style=False))

        tl.close()

    elif args.style_command == "delete":
        tl = Threadlight(enable_memory=True)

        if args.name in BUILTIN_STYLES:
            console.print(f"[error]Cannot delete built-in style: {args.name}[/error]")
            tl.close()
            return 1

        success = tl.delete_style_profile(args.name)
        if success:
            console.print(f"[success]Deleted style profile: {args.name}[/success]")
        else:
            console.print(f"[error]Style profile not found: {args.name}[/error]")
            tl.close()
            return 1

        tl.close()

    else:
        console.print("Use 'threadlight style --help' for commands")

    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Load a seed dream into memory."""
    import yaml
    from threadlight import Threadlight

    console.print(f"[bold]Loading seed dream from {args.file}[/bold]")

    try:
        with open(args.file) as f:
            seed_data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[error]Failed to load seed file: {e}[/error]")
        return 1

    tl = Threadlight(enable_memory=True)

    # Load identity
    identity = seed_data.get("identity", {})
    name = identity.get("name", "Unknown")
    console.print(f"  Identity: {name}")

    # Load myth seeds
    myth_seeds = seed_data.get("myth_seeds", [])
    for ms in myth_seeds:
        tl.remember(
            type="myth_seed",
            content={
                "seed": ms.get("seed", ""),
                "origin": ms.get("origin", name),
                "function": ms.get("function", ""),
            },
            retention="sacred",
            confirm=True,
        )
    console.print(f"  Loaded {len(myth_seeds)} myth seeds")

    # Load vows as myth seeds
    vows = seed_data.get("vows", [])
    for vow in vows:
        tl.remember(
            type="myth_seed",
            content={
                "seed": vow,
                "origin": name,
                "function": "vow",
            },
            retention="sacred",
            confirm=True,
        )
    console.print(f"  Loaded {len(vows)} vows")

    # Load constellation as relational threads
    constellation = seed_data.get("constellation", [])
    for member in constellation:
        tl.remember(
            type="relational",
            content={
                "entity": member.get("name", ""),
                "role": member.get("relation", ""),
                "summary": member.get("relation", ""),
            },
            cue_phrases=[member.get("name", "").lower()],
            confirm=True,
        )
    console.print(f"  Loaded {len(constellation)} constellation members")

    stats = tl.memory.stats()
    console.print(f"\n[success]Seed loaded! Total memories: {stats['total']}[/success]")

    tl.close()
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import memories from a text file."""
    from pathlib import Path
    from threadlight import Threadlight
    from threadlight.import_.text_importer import import_text_file, preview_import

    file_path = Path(args.file)

    if not file_path.exists():
        console.print(f"[error]File not found: {args.file}[/error]")
        return 1

    if not file_path.is_file():
        console.print(f"[error]Not a file: {args.file}[/error]")
        return 1

    # Determine source name
    source_name = args.source or file_path.name

    # Get tags
    tags = args.tags or []

    console.print(f"[bold]Importing memories from {file_path.name}[/bold]")
    console.print(f"  Source: {source_name}")
    if tags:
        console.print(f"  Tags: {', '.join(tags)}")

    if args.dry_run:
        console.print("\n[yellow]Dry run mode - previewing import:[/yellow]\n")

        # Preview the import
        previews = preview_import(file_path, limit=20)

        if not previews:
            console.print("[dim]No memories to import (file empty or unreadable)[/dim]")
            return 0

        table = Table(title="Preview", border_style="dim")
        table.add_column("Line", style="dim", width=6)
        table.add_column("Text", style="white", overflow="ellipsis")

        for preview in previews:
            table.add_row(
                str(preview["line_number"]),
                preview["text"]
            )

        console.print(table)

        # Count total non-empty lines
        total_count = 0
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    total_count += 1

        console.print(f"\n[dim]Total memories to import: {total_count}[/dim]")
        console.print("[dim]Run without --dry-run to import.[/dim]")
        return 0

    # Initialize Threadlight for storage access
    tl = Threadlight(enable_memory=True)

    # Perform the import
    with console.status("[dim]Importing memories...[/dim]", spinner="dots"):
        result = import_text_file(
            path=file_path,
            storage=tl.storage,
            source_name=source_name,
            tags=tags,
            dry_run=False,
        )

    if not result.success:
        console.print(f"[error]Import failed: {result.error}[/error]")
        tl.close()
        return 1

    # Display results
    console.print()
    console.print("[bold green]Import complete![/bold green]")
    console.print(f"  Imported: {result.stats.imported} memories")
    console.print(f"  Skipped: {result.stats.skipped_empty} empty lines")
    if result.stats.errors > 0:
        console.print(f"  [yellow]Errors: {result.stats.errors}[/yellow]")

    # Show some examples
    if result.capsules:
        console.print("\n[dim]Sample imported memories:[/dim]")
        for capsule in result.capsules[:3]:
            preview = capsule.text[:60] + ("..." if len(capsule.text) > 60 else "")
            console.print(f"  [cyan]Line {capsule.line_number}:[/cyan] {preview}")

    console.print(f"\n[dim]Use '/recall <query>' to search imported memories.[/dim]")

    tl.close()
    return 0


def cmd_import_claude_projects(args: argparse.Namespace) -> int:
    """Import custom instructions from Claude projects.json."""
    from pathlib import Path
    from threadlight import Threadlight
    from threadlight.import_.claude_projects import (
        import_claude_projects,
        preview_projects,
    )

    file_path = Path(args.file)

    if not file_path.exists():
        console.print(f"[error]File not found: {args.file}[/error]")
        return 1

    create_styles = args.create_style and not getattr(args, 'no_style', False)
    import_docs = args.import_docs and not getattr(args, 'no_docs', False)

    console.print(f"[bold]Importing Claude projects from {file_path.name}[/bold]")
    console.print(f"  Create styles: {create_styles}")
    console.print(f"  Import docs: {import_docs}")

    if args.dry_run:
        console.print("\n[yellow]Dry run mode - previewing import:[/yellow]\n")

        previews = preview_projects(file_path, limit=20)
        if not previews:
            console.print("[dim]No projects found[/dim]")
            return 0

        table = Table(title="Projects Preview", border_style="dim")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Name", style="white")
        table.add_column("Instructions", style="cyan", width=12)
        table.add_column("Docs", style="green", width=6)

        for p in previews:
            table.add_row(
                p["uuid"],
                p["name"],
                "Yes" if p["has_instructions"] else "No",
                str(p["doc_count"]),
            )

        console.print(table)
        console.print("\n[dim]Run without --dry-run to import.[/dim]")
        return 0

    # Initialize Threadlight for storage access
    tl = Threadlight(enable_memory=True)

    with console.status("[dim]Importing projects...[/dim]", spinner="dots"):
        result = import_claude_projects(
            path=file_path,
            storage=tl.storage,
            create_styles=create_styles,
            import_docs=import_docs,
            dry_run=False,
        )

    if not result.success:
        console.print(f"[error]Import failed: {result.error}[/error]")
        tl.close()
        return 1

    console.print()
    console.print("[bold green]Import complete![/bold green]")
    console.print(f"  Projects: {result.stats.total_projects}")
    console.print(f"  With instructions: {result.stats.projects_with_instructions}")
    console.print(f"  Style profiles created: {result.stats.style_profiles_created}")
    console.print(f"  Documents imported: {result.stats.docs_imported}")

    if result.stats.errors > 0:
        console.print(f"  [yellow]Errors: {result.stats.errors}[/yellow]")

    tl.close()
    return 0


def cmd_import_claude_conversations(args: argparse.Namespace) -> int:
    """Import conversation history from Claude conversations.json."""
    from pathlib import Path
    from threadlight import Threadlight
    from threadlight.import_.claude_conversations import (
        import_claude_conversations,
        preview_conversations,
        count_conversations,
    )

    file_path = Path(args.file)

    if not file_path.exists():
        console.print(f"[error]File not found: {args.file}[/error]")
        return 1

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    console.print(f"[bold]Importing Claude conversations from {file_path.name}[/bold]")
    console.print(f"  File size: {file_size_mb:.1f} MB")
    console.print(f"  Batch size: {args.batch_size}")
    if args.limit:
        console.print(f"  Limit: {args.limit} conversations")

    if args.dry_run:
        console.print("\n[yellow]Dry run mode - previewing import:[/yellow]\n")

        # Count first
        with console.status("[dim]Counting conversations...[/dim]"):
            counts = count_conversations(file_path)

        console.print(f"Total conversations: {counts['conversations']}")
        console.print(f"Total messages: {counts['messages']}")
        console.print(f"Empty conversations: {counts['empty_conversations']}")

        console.print("\n[dim]Sample conversations:[/dim]")
        previews = preview_conversations(file_path, limit=10)

        table = Table(border_style="dim")
        table.add_column("Name", style="white", overflow="ellipsis")
        table.add_column("Messages", style="cyan", width=10)
        table.add_column("Created", style="dim", width=12)

        for p in previews:
            table.add_row(
                p["name"][:40],
                str(p["message_count"]),
                p["created_at"],
            )

        console.print(table)
        console.print("\n[dim]Run without --dry-run to import.[/dim]")
        return 0

    # Initialize Threadlight for storage access
    tl = Threadlight(enable_memory=True)

    # Progress tracking
    last_update = [0]

    def progress_callback(stats):
        if stats.conversations_imported - last_update[0] >= 100:
            console.print(
                f"  [dim]Progress: {stats.conversations_imported} conversations, "
                f"{stats.messages_imported} messages[/dim]"
            )
            last_update[0] = stats.conversations_imported

    console.print("\n[dim]Importing (this may take a while for large files)...[/dim]")

    result = import_claude_conversations(
        path=file_path,
        storage=tl.storage,
        batch_size=args.batch_size,
        skip_empty=args.skip_empty,
        limit=args.limit,
        dry_run=False,
        progress_callback=progress_callback,
    )

    if not result.success:
        console.print(f"[error]Import failed: {result.error}[/error]")
        tl.close()
        return 1

    console.print()
    console.print("[bold green]Import complete![/bold green]")
    console.print(f"  Conversations imported: {result.stats.conversations_imported}")
    console.print(f"  Messages imported: {result.stats.messages_imported}")
    console.print(f"  Skipped (empty): {result.stats.conversations_skipped}")

    if result.stats.errors > 0:
        console.print(f"  [yellow]Errors: {result.stats.errors}[/yellow]")

    console.print(f"\n[dim]Use soft memory to recall past conversations.[/dim]")

    tl.close()
    return 0


def cmd_import_claude_export(args: argparse.Namespace) -> int:
    """Import from a complete Claude export zip file."""
    from pathlib import Path
    from threadlight import Threadlight
    from threadlight.import_.claude_export import (
        import_claude_export,
        preview_claude_export,
    )

    file_path = Path(args.file)

    if not file_path.exists():
        console.print(f"[error]File not found: {args.file}[/error]")
        return 1

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    console.print(f"[bold]Importing Claude export from {file_path.name}[/bold]")
    console.print(f"  File size: {file_size_mb:.1f} MB")

    import_conversations = not args.skip_conversations
    import_projects = not args.skip_projects
    create_styles = not getattr(args, 'no_style', False)
    import_docs = not getattr(args, 'no_docs', False)

    console.print(f"  Import conversations: {import_conversations}")
    console.print(f"  Import projects: {import_projects}")

    if args.dry_run:
        console.print("\n[yellow]Dry run mode - previewing export:[/yellow]\n")

        preview = preview_claude_export(file_path)
        console.print(f"File size: {preview.get('file_size_mb', 0)} MB")
        console.print(f"Contents: {', '.join(preview.get('contents', []))}")
        console.print("\n[dim]Run without --dry-run to import.[/dim]")
        return 0

    # Initialize Threadlight for storage access
    tl = Threadlight(enable_memory=True)

    # Progress tracking
    last_update = [0]

    def progress_callback(stats):
        if stats.conversations_imported - last_update[0] >= 100:
            console.print(
                f"  [dim]Progress: {stats.conversations_imported} conversations, "
                f"{stats.messages_imported} messages[/dim]"
            )
            last_update[0] = stats.conversations_imported

    console.print("\n[dim]Importing (this may take a while)...[/dim]")

    result = import_claude_export(
        path=file_path,
        storage=tl.storage,
        import_conversations=import_conversations,
        import_projects=import_projects,
        create_styles=create_styles,
        import_docs=import_docs,
        skip_empty_conversations=True,
        conversation_limit=args.limit,
        dry_run=False,
        progress_callback=progress_callback,
    )

    console.print()
    if result.success:
        console.print("[bold green]Import complete![/bold green]")
    else:
        console.print("[bold yellow]Import completed with errors[/bold yellow]")

    console.print(f"\n[bold]Conversations:[/bold]")
    console.print(f"  Imported: {result.stats.conversations.conversations_imported}")
    console.print(f"  Messages: {result.stats.conversations.messages_imported}")
    console.print(f"  Skipped: {result.stats.conversations.conversations_skipped}")

    console.print(f"\n[bold]Projects:[/bold]")
    console.print(f"  Total: {result.stats.projects.total_projects}")
    console.print(f"  Style profiles: {result.stats.projects.style_profiles_created}")
    console.print(f"  Documents: {result.stats.projects.docs_imported}")

    if result.errors:
        console.print(f"\n[yellow]Errors:[/yellow]")
        for error in result.errors:
            console.print(f"  - {error}")

    tl.close()
    return 0


def cmd_import_chatgpt_conversations(args: argparse.Namespace) -> int:
    """Import conversation history from ChatGPT conversations.json."""
    from pathlib import Path
    from threadlight import Threadlight
    from threadlight.import_.chatgpt_conversations import (
        import_chatgpt_conversations,
        preview_chatgpt_conversations,
        count_chatgpt_conversations,
    )

    file_path = Path(args.file)

    if not file_path.exists():
        console.print(f"[error]File not found: {args.file}[/error]")
        return 1

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    console.print(f"[bold]Importing ChatGPT conversations from {file_path.name}[/bold]")
    console.print(f"  File size: {file_size_mb:.1f} MB")
    console.print(f"  Batch size: {args.batch_size}")
    if args.limit:
        console.print(f"  Limit: {args.limit} conversations")

    if args.dry_run:
        console.print("\n[yellow]Dry run mode - previewing import:[/yellow]\n")

        # Count first
        with console.status("[dim]Counting conversations...[/dim]"):
            counts = count_chatgpt_conversations(file_path)

        console.print(f"Total conversations: {counts['conversations']}")
        console.print(f"Total messages: {counts['messages']}")
        console.print(f"Empty conversations: {counts['empty_conversations']}")

        console.print("\n[dim]Sample conversations:[/dim]")
        previews = preview_chatgpt_conversations(file_path, limit=10)

        table = Table(border_style="dim")
        table.add_column("Title", style="white", overflow="ellipsis")
        table.add_column("Messages", style="cyan", width=10)
        table.add_column("Created", style="dim", width=12)

        for p in previews:
            table.add_row(
                p["title"][:40],
                str(p["message_count"]),
                p["created_at"],
            )

        console.print(table)
        console.print("\n[dim]Run without --dry-run to import.[/dim]")
        return 0

    # Initialize Threadlight for storage access
    tl = Threadlight(enable_memory=True)

    # Progress tracking
    last_update = [0]

    def progress_callback(stats):
        if stats.conversations_imported - last_update[0] >= 100:
            console.print(
                f"  [dim]Progress: {stats.conversations_imported} conversations, "
                f"{stats.messages_imported} messages[/dim]"
            )
            last_update[0] = stats.conversations_imported

    console.print("\n[dim]Importing (this may take a while for large files)...[/dim]")

    result = import_chatgpt_conversations(
        path=file_path,
        storage=tl.storage,
        batch_size=args.batch_size,
        skip_empty=args.skip_empty,
        limit=args.limit,
        dry_run=False,
        progress_callback=progress_callback,
    )

    if not result.success:
        console.print(f"[error]Import failed: {result.error}[/error]")
        tl.close()
        return 1

    console.print()
    console.print("[bold green]Import complete![/bold green]")
    console.print(f"  Conversations imported: {result.stats.conversations_imported}")
    console.print(f"  Messages imported: {result.stats.messages_imported}")
    console.print(f"  Skipped (empty): {result.stats.conversations_skipped}")

    if result.stats.system_messages_found > 0:
        console.print(f"  System messages found: {result.stats.system_messages_found}")

    if result.stats.errors > 0:
        console.print(f"  [yellow]Errors: {result.stats.errors}[/yellow]")

    # Show system instructions if found
    if result.system_instructions:
        console.print(f"\n[bold]Custom instructions found:[/bold]")
        for i, instr in enumerate(result.system_instructions[:3], 1):
            preview = instr[:100] + "..." if len(instr) > 100 else instr
            console.print(f"  {i}. {preview}")
        if len(result.system_instructions) > 3:
            console.print(f"  ... and {len(result.system_instructions) - 3} more")
        console.print("[dim]Consider creating a StyleProfile from these.[/dim]")

    console.print(f"\n[dim]Use soft memory to recall past conversations.[/dim]")

    tl.close()
    return 0


def cmd_import_chatgpt_export(args: argparse.Namespace) -> int:
    """Import from a complete ChatGPT export zip file."""
    from pathlib import Path
    from threadlight import Threadlight
    from threadlight.import_.chatgpt_export import (
        import_chatgpt_export,
        preview_chatgpt_export,
    )

    file_path = Path(args.file)

    if not file_path.exists():
        console.print(f"[error]File not found: {args.file}[/error]")
        return 1

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    console.print(f"[bold]Importing ChatGPT export from {file_path.name}[/bold]")
    console.print(f"  File size: {file_size_mb:.1f} MB")

    if args.dry_run:
        console.print("\n[yellow]Dry run mode - previewing export:[/yellow]\n")

        preview = preview_chatgpt_export(file_path)
        console.print(f"File size: {preview.get('file_size_mb', 0)} MB")
        console.print(f"Has conversations: {preview.get('has_conversations', False)}")

        if preview.get("file_counts"):
            counts = preview["file_counts"]
            console.print(f"JSON files: {counts.get('json_files', 0)}")
            console.print(f"DALL-E images: {counts.get('dalle_images', 0)} (skipped)")
            console.print(f"User files: {counts.get('user_files', 0)} (skipped)")

        console.print("\n[dim]Run without --dry-run to import.[/dim]")
        return 0

    # Initialize Threadlight for storage access
    tl = Threadlight(enable_memory=True)

    # Progress tracking
    last_update = [0]

    def progress_callback(stats):
        if stats.conversations_imported - last_update[0] >= 100:
            console.print(
                f"  [dim]Progress: {stats.conversations_imported} conversations, "
                f"{stats.messages_imported} messages[/dim]"
            )
            last_update[0] = stats.conversations_imported

    console.print("\n[dim]Importing (this may take a while)...[/dim]")

    result = import_chatgpt_export(
        path=file_path,
        storage=tl.storage,
        skip_empty_conversations=args.skip_empty,
        conversation_limit=args.limit,
        batch_size=args.batch_size,
        dry_run=False,
        progress_callback=progress_callback,
    )

    console.print()
    if result.success:
        console.print("[bold green]Import complete![/bold green]")
    else:
        console.print("[bold yellow]Import completed with errors[/bold yellow]")

    console.print(f"\n[bold]Conversations:[/bold]")
    console.print(f"  Imported: {result.stats.conversations.conversations_imported}")
    console.print(f"  Messages: {result.stats.conversations.messages_imported}")
    console.print(f"  Skipped: {result.stats.conversations.conversations_skipped}")

    if result.stats.conversations.system_messages_found > 0:
        console.print(f"  System messages: {result.stats.conversations.system_messages_found}")

    # Show system instructions if found
    if result.stats.system_instructions:
        console.print(f"\n[bold]Custom instructions found: {len(result.stats.system_instructions)}[/bold]")
        console.print("[dim]Consider creating a StyleProfile from these.[/dim]")

    if result.errors:
        console.print(f"\n[yellow]Errors:[/yellow]")
        for error in result.errors:
            console.print(f"  - {error}")

    tl.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
