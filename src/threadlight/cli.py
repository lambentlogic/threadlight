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
    "assistant": "magenta",
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
  [cyan]/profile <cmd>[/cyan]       Manage profiles (list, create, switch, show, delete)
  [cyan]/help[/cyan]                Show this message
  [cyan]/quit[/cyan]                Exit Threadlight

[bold]Profiles:[/bold]

  [dim]Profiles are persistent personas with their own memories and model configs.
  /profile list              - List all profiles
  /profile create <name>     - Create a new profile
  /profile switch <id/name>  - Switch to a profile
  /profile show <id>         - Show profile details
  /profile delete <id>       - Delete a profile
  /profile export <id>       - Export profile to JSON
  /profile import <file>     - Import profile from JSON[/dim]

[bold]Rituals:[/bold]

  [dim]Rituals are meaningful gestures that emerge through relationship.
  Create your own rituals with /remember ritual.
  Invoke any ritual directly by name (e.g., /my-ritual).[/dim]

[bold]Style Profiles:[/bold]

  [dim]Available built-in styles: minimal, professional, creative
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
    table.add_column("Model", style="magenta", width=15)
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

        # Model scope display
        model_scope = getattr(c, 'model_scope', None)
        if model_scope is None:
            scope_str = "[green]shared[/green]"
        else:
            scope_str = model_scope[:12] + "..." if len(model_scope) > 15 else model_scope

        table.add_row(
            c.id[:8] + "...",
            c.type.value,
            scope_str,
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
        self.identity = identity or "Assistant"
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

        console.print(f"[dim]Connected as [/dim][assistant]{self.identity}[/assistant]")
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

        elif command == "/profile" or command == "/profiles":
            self.handle_profile(args)

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
            console.print(f"\n[bold assistant]{self.identity}:[/bold assistant] {response}\n")

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
        # Support both old and new names for identity phrases
        valid_types = ["relational", "identity_phrase", "myth_seed", "ritual", "witness", "style"]

        if not type_str or type_str not in valid_types:
            console.print(f"\n[bold]Memory Types:[/bold]")
            console.print("  [cyan]relational[/cyan]       - Track a relationship")
            console.print("  [cyan]identity_phrase[/cyan]  - A core belief or mantra")
            console.print("  [cyan]ritual[/cyan]           - A repeated meaningful gesture")
            console.print("  [cyan]witness[/cyan]          - A moment of being seen")
            console.print("\n[dim]Usage: /remember <type>[/dim]\n")
            return

        try:
            if type_str == "relational":
                entity = console.input("[dim]Entity name:[/dim] ")
                summary = console.input("[dim]Summary:[/dim] ")
                quality = console.input("[dim]Quality (e.g., warm, playful, dreamlike):[/dim] ")

                capsule = self.tl.remember(
                    type="relational",
                    content={
                        "entity": entity,
                        "summary": summary,
                        "quality": quality,
                    },
                    cue_phrases=[entity.lower()],
                    confirm=True,
                )
                console.print(f"\n[success]Created memory: {capsule.id[:8]}...[/success]\n")

            elif type_str in ("myth_seed", "identity_phrase"):
                seed = console.input("[dim]The phrase:[/dim] ")
                origin = console.input("[dim]Origin (optional):[/dim] ")

                capsule = self.tl.remember(
                    type="myth_seed",  # Internal type name
                    content={
                        "seed": seed,
                        "origin": origin,
                    },
                    retention="sacred",
                    confirm=True,
                )
                console.print(f"\n[success]Created identity phrase: {capsule.id[:8]}...[/success]\n")

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

    def handle_profile(self, args: str) -> None:
        """Handle profile commands."""
        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ""
        subargs = parts[1] if len(parts) > 1 else ""

        if not subcmd or subcmd == "list":
            self._profile_list()
        elif subcmd == "create":
            self._profile_create(subargs)
        elif subcmd == "switch":
            self._profile_switch(subargs)
        elif subcmd == "show":
            self._profile_show(subargs)
        elif subcmd == "delete":
            self._profile_delete(subargs)
        elif subcmd == "export":
            self._profile_export(subargs)
        elif subcmd == "import":
            self._profile_import(subargs)
        elif subcmd == "clear":
            self._profile_clear()
        else:
            console.print(f"[warning]Unknown profile command: {subcmd}[/warning]")
            console.print("[dim]Available: list, create, switch, show, delete, export, import, clear[/dim]")

    def _profile_list(self) -> None:
        """List all profiles."""
        try:
            profiles = self.tl.list_profiles()
            active = self.tl.get_active_profile()

            if not profiles:
                console.print("\n[dim]No profiles found. Create one with /profile create <name>[/dim]\n")
                return

            console.print("\n[bold]Profiles[/bold]\n")

            table = Table(border_style="dim")
            table.add_column("ID", style="dim", width=10)
            table.add_column("Name", style="white")
            table.add_column("Model", style="cyan", width=25)
            table.add_column("Style", style="magenta", width=12)
            table.add_column("Updated", style="dim", width=16)

            for p in profiles:
                pid = p.id[:8] + "..."
                name = p.name
                if active and p.id == active.id:
                    name = f"[green]* {name}[/green]"

                model = p.primary_model
                if len(model) > 25:
                    model = model[:22] + "..."

                style = p.style_profile_id or "[dim]-[/dim]"
                updated = p.updated_at.strftime("%Y-%m-%d %H:%M")

                table.add_row(pid, name, model, style, updated)

            console.print(table)
            console.print("\n[dim]* = active profile[/dim]\n")

        except Exception as e:
            console.print(f"[error]Failed to list profiles: {e}[/error]")

    def _profile_create(self, args: str) -> None:
        """Create a new profile interactively."""
        if not args:
            console.print("[warning]Usage: /profile create <name>[/warning]")
            return

        try:
            name = args.strip()
            console.print(f"\n[bold]Creating profile: {name}[/bold]\n")

            # Get optional settings
            description = console.input("[dim]Description (optional):[/dim] ").strip()

            model = console.input(f"[dim]Model (default: {self.tl.config.provider.model}):[/dim] ").strip()
            if not model:
                model = self.tl.config.provider.model

            system_prompt = console.input("[dim]System prompt (optional, multiline with \\n):[/dim] ").strip()
            system_prompt = system_prompt.replace("\\n", "\n")

            style_id = console.input("[dim]Style profile ID (optional):[/dim] ").strip() or None

            color = console.input("[dim]Color hex (optional, e.g., #6366f1):[/dim] ").strip() or None

            # Create the profile
            profile = self.tl.create_profile(
                name=name,
                description=description,
                primary_model=model,
                system_prompt=system_prompt,
                style_profile_id=style_id,
                color=color,
            )

            console.print(f"\n[success]Created profile: {profile.name} ({profile.id[:8]}...)[/success]")
            console.print(f"[dim]Switch to it with: /profile switch {profile.id[:8]}[/dim]\n")

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled.[/dim]")
        except Exception as e:
            console.print(f"[error]Failed to create profile: {e}[/error]")

    def _profile_switch(self, args: str) -> None:
        """Switch to a profile."""
        if not args:
            console.print("[warning]Usage: /profile switch <profile_id or name>[/warning]")
            return

        try:
            identifier = args.strip()

            # Try to find by ID first (or partial ID)
            profiles = self.tl.list_profiles()
            match = None

            for p in profiles:
                if p.id.startswith(identifier) or p.name.lower() == identifier.lower():
                    match = p
                    break

            if not match:
                console.print(f"[error]Profile not found: {identifier}[/error]")
                return

            self.tl.switch_profile(match.id)
            self.identity = match.name  # Update REPL identity

            console.print(f"\n[success]Switched to profile: {match.name}[/success]")
            console.print(f"[dim]Model: {match.primary_model}[/dim]")
            if match.style_profile_id:
                console.print(f"[dim]Style: {match.style_profile_id}[/dim]")
            console.print()

        except Exception as e:
            console.print(f"[error]Failed to switch profile: {e}[/error]")

    def _profile_show(self, args: str) -> None:
        """Show profile details."""
        if not args:
            # Show active profile
            profile = self.tl.get_active_profile()
            if not profile:
                console.print("[dim]No active profile. Use /profile show <id> to view one.[/dim]")
                return
        else:
            # Find by ID or name
            identifier = args.strip()
            profiles = self.tl.list_profiles()
            profile = None

            for p in profiles:
                if p.id.startswith(identifier) or p.name.lower() == identifier.lower():
                    profile = p
                    break

            if not profile:
                console.print(f"[error]Profile not found: {identifier}[/error]")
                return

        try:
            active = self.tl.get_active_profile()
            is_active = active and profile.id == active.id

            console.print(f"\n[bold]Profile: {profile.name}[/bold]")
            if is_active:
                console.print("[green](active)[/green]")

            console.print(f"\n[dim]ID:[/dim] {profile.id}")
            console.print(f"[dim]Description:[/dim] {profile.description or '[none]'}")
            console.print(f"[dim]Model:[/dim] {profile.primary_model}")
            console.print(f"[dim]Temperature:[/dim] {profile.temperature}")
            console.print(f"[dim]Style:[/dim] {profile.style_profile_id or '[none]'}")
            console.print(f"[dim]Memory Scope:[/dim] {profile.memory_scope}")
            console.print(f"[dim]Access Shared:[/dim] {profile.access_shared_memories}")
            console.print(f"[dim]Color:[/dim] {profile.color or '[none]'}")
            console.print(f"[dim]Created:[/dim] {profile.created_at.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"[dim]Updated:[/dim] {profile.updated_at.strftime('%Y-%m-%d %H:%M')}")

            if profile.system_prompt:
                console.print("\n[dim]System Prompt:[/dim]")
                prompt = profile.system_prompt
                if len(prompt) > 200:
                    prompt = prompt[:200] + "..."
                console.print(f"  {prompt}")

            console.print()

        except Exception as e:
            console.print(f"[error]Failed to show profile: {e}[/error]")

    def _profile_delete(self, args: str) -> None:
        """Delete a profile."""
        if not args:
            console.print("[warning]Usage: /profile delete <profile_id>[/warning]")
            return

        try:
            identifier = args.strip()

            # Find by ID or name
            profiles = self.tl.list_profiles()
            profile = None

            for p in profiles:
                if p.id.startswith(identifier) or p.name.lower() == identifier.lower():
                    profile = p
                    break

            if not profile:
                console.print(f"[error]Profile not found: {identifier}[/error]")
                return

            # Confirm deletion
            confirm = console.input(f"[warning]Delete profile '{profile.name}'? (y/N):[/warning] ")
            if confirm.lower() != 'y':
                console.print("[dim]Cancelled.[/dim]")
                return

            success = self.tl.delete_profile(profile.id)
            if success:
                console.print(f"[success]Deleted profile: {profile.name}[/success]")
            else:
                console.print(f"[error]Failed to delete profile[/error]")

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled.[/dim]")
        except Exception as e:
            console.print(f"[error]Failed to delete profile: {e}[/error]")

    def _profile_export(self, args: str) -> None:
        """Export a profile to JSON."""
        if not args:
            console.print("[warning]Usage: /profile export <profile_id> [--include-memories][/warning]")
            return

        try:
            parts = args.split()
            identifier = parts[0]
            include_memories = "--include-memories" in args or "-m" in args

            # Find by ID or name
            profiles = self.tl.list_profiles()
            profile = None

            for p in profiles:
                if p.id.startswith(identifier) or p.name.lower() == identifier.lower():
                    profile = p
                    break

            if not profile:
                console.print(f"[error]Profile not found: {identifier}[/error]")
                return

            export_data = self.tl.export_profile(profile.id, include_memories=include_memories)

            # Save to file
            import json
            filename = f"profile_{profile.name.lower().replace(' ', '_')}_{profile.id[:8]}.json"
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)

            console.print(f"\n[success]Exported profile to: {filename}[/success]")
            if include_memories:
                console.print(f"[dim]Included {len(export_data.get('memories', []))} memories[/dim]")
            console.print()

        except Exception as e:
            console.print(f"[error]Failed to export profile: {e}[/error]")

    def _profile_import(self, args: str) -> None:
        """Import a profile from JSON."""
        if not args:
            console.print("[warning]Usage: /profile import <file.json>[/warning]")
            return

        try:
            import json
            filename = args.strip()

            with open(filename, 'r') as f:
                export_data = json.load(f)

            profile = self.tl.import_profile(export_data)

            console.print(f"\n[success]Imported profile: {profile.name} ({profile.id[:8]}...)[/success]")
            console.print(f"[dim]Switch to it with: /profile switch {profile.id[:8]}[/dim]\n")

        except FileNotFoundError:
            console.print(f"[error]File not found: {args}[/error]")
        except json.JSONDecodeError:
            console.print(f"[error]Invalid JSON file[/error]")
        except Exception as e:
            console.print(f"[error]Failed to import profile: {e}[/error]")

    def _profile_clear(self) -> None:
        """Clear the active profile."""
        try:
            active = self.tl.get_active_profile()
            if not active:
                console.print("[dim]No active profile to clear.[/dim]")
                return

            self.tl.clear_profile()
            self.identity = self.identity or "Assistant"

            console.print("[success]Cleared active profile. Using default settings.[/success]")

        except Exception as e:
            console.print(f"[error]Failed to clear profile: {e}[/error]")


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
    chat_parser.add_argument("--identity", help="Identity name", default="Assistant")

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory management")
    memory_sub = memory_parser.add_subparsers(dest="memory_command")

    memory_list_parser = memory_sub.add_parser("list", help="List memory capsules")
    memory_list_parser.add_argument(
        "--model",
        help="Filter by model scope (use 'shared' for shared memories)"
    )
    memory_list_parser.add_argument(
        "--include-shared",
        action="store_true",
        default=True,
        help="Include shared memories when filtering by model (default: true)"
    )
    memory_list_parser.add_argument(
        "--no-shared",
        action="store_true",
        help="Exclude shared memories when filtering by model"
    )

    memory_sub.add_parser("stats", help="Show memory statistics")
    memory_sub.add_parser("export", help="Export memories to JSON")
    memory_sub.add_parser("decay", help="Run decay cycle")

    import_parser = memory_sub.add_parser("import", help="Import memories from JSON")
    import_parser.add_argument("file", help="JSON file to import")

    # Model scope subcommands
    scope_parser = memory_sub.add_parser("scope", help="Model scope management")
    scope_sub = scope_parser.add_subparsers(dest="scope_command")

    scope_sub.add_parser("status", help="Show per-model isolation status")
    scope_sub.add_parser("stats", help="Show memory counts per model")

    scope_enable = scope_sub.add_parser("enable", help="Enable per-model memory isolation")
    scope_enable.add_argument(
        "--default-shared",
        action="store_true",
        help="Make new memories shared by default"
    )

    scope_sub.add_parser("disable", help="Disable per-model memory isolation")

    scope_share = scope_sub.add_parser("share", help="Make a memory shared across all models")
    scope_share.add_argument("capsule_id", help="Memory ID to share")

    scope_assign = scope_sub.add_parser("assign", help="Assign a memory to a specific model")
    scope_assign.add_argument("capsule_id", help="Memory ID to assign")
    scope_assign.add_argument("--model", help="Model to assign to (default: current model)")

    # Embeddings commands
    embeddings_parser = subparsers.add_parser("embeddings", help="Embedding management for semantic search")
    embeddings_sub = embeddings_parser.add_subparsers(dest="embeddings_command")

    embeddings_generate_parser = embeddings_sub.add_parser("generate", help="Generate embeddings for memories and conversations")
    embeddings_generate_parser.add_argument(
        "--memories-only",
        action="store_true",
        help="Only generate embeddings for memories (skip conversations)"
    )
    embeddings_generate_parser.add_argument(
        "--conversations-only",
        action="store_true",
        help="Only generate embeddings for conversations (skip memories)"
    )

    embeddings_sub.add_parser("stats", help="Show embedding statistics")

    embeddings_enable_parser = embeddings_sub.add_parser("enable", help="Enable embeddings")
    embeddings_enable_parser.add_argument(
        "--provider",
        default="local",
        choices=["local", "openai", "nous"],
        help="Embedding provider (default: local)"
    )
    embeddings_enable_parser.add_argument(
        "--model",
        default="intfloat/e5-small-v2",
        help="Model name (default: intfloat/e5-small-v2)"
    )

    embeddings_sub.add_parser("disable", help="Disable embeddings")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search memories and conversations")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--semantic",
        action="store_true",
        help="Use semantic search (requires embeddings)"
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results (default: 10)"
    )
    search_parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Minimum similarity threshold for semantic search (default: 0.5)"
    )
    search_parser.add_argument(
        "--memories-only",
        action="store_true",
        help="Only search memories"
    )
    search_parser.add_argument(
        "--conversations-only",
        action="store_true",
        help="Only search conversations"
    )

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
    style_create_parser.add_argument("--tone", default="", help="Base tone (for structured styles)")
    style_create_parser.add_argument("--permission", "-p", action="append", dest="permissions", help="Add permission (for structured styles)")
    style_create_parser.add_argument("--constraint", "-c", action="append", dest="constraints", help="Add constraint (for structured styles)")
    style_create_parser.add_argument("--freeform", "-f", dest="freeform_description", help="Freeform style definition (use instead of structured fields)")

    style_edit_parser = style_sub.add_parser("edit", help="Edit a style profile")
    style_edit_parser.add_argument("name", help="Style profile name to edit")

    style_set_parser = style_sub.add_parser("set", help="Set active style profile")
    style_set_parser.add_argument("name", nargs="?", help="Style profile name (omit to clear)")

    style_show_parser = style_sub.add_parser("show", help="Show a style profile")
    style_show_parser.add_argument("name", help="Style profile name")

    style_delete_parser = style_sub.add_parser("delete", help="Delete a style profile")
    style_delete_parser.add_argument("name", help="Style profile name to delete")

    # Memory Type command
    memtype_parser = subparsers.add_parser("memory-type", help="Custom memory type management")
    memtype_sub = memtype_parser.add_subparsers(dest="memory_type_command")

    memtype_sub.add_parser("list", help="List all memory types")

    memtype_create_parser = memtype_sub.add_parser("create", help="Create a new custom memory type")
    memtype_create_parser.add_argument("type_id", help="Type identifier (e.g., creative_project)")
    memtype_create_parser.add_argument("--name", help="Display name (defaults to type_id)")
    memtype_create_parser.add_argument("--description", "-d", default="", help="Type description")
    memtype_create_parser.add_argument(
        "--field", "-f",
        action="append",
        dest="fields",
        help="Field definition: name:type[:required]. E.g., title:string:required or notes:text"
    )
    memtype_create_parser.add_argument("--template", "-t", help="Display template, e.g., '{title} ({status})'")
    memtype_create_parser.add_argument("--icon", default="file-text", help="Icon name for UI")

    memtype_show_parser = memtype_sub.add_parser("show", help="Show a memory type definition")
    memtype_show_parser.add_argument("type_id", help="Type identifier to show")

    memtype_delete_parser = memtype_sub.add_parser("delete", help="Delete a custom memory type")
    memtype_delete_parser.add_argument("type_id", help="Type identifier to delete")
    memtype_delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    memtype_sub.add_parser("examples", help="List available example types")

    memtype_import_parser = memtype_sub.add_parser("import", help="Import an example type")
    memtype_import_parser.add_argument(
        "type_id",
        help="Example type to import: creative_project, book_note, dream_log, location"
    )

    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Profile management")
    profile_sub = profile_parser.add_subparsers(dest="profile_command")

    profile_sub.add_parser("list", help="List all profiles")

    profile_create_parser = profile_sub.add_parser("create", help="Create a new profile")
    profile_create_parser.add_argument("name", help="Profile display name")
    profile_create_parser.add_argument("--model", "-m", help="Primary model to use")
    profile_create_parser.add_argument("--description", "-d", default="", help="Profile description")
    profile_create_parser.add_argument("--system-prompt", "-s", help="System prompt")
    profile_create_parser.add_argument("--style", help="Style profile ID to use")
    profile_create_parser.add_argument("--color", help="Hex color for UI (e.g., #6366f1)")
    profile_create_parser.add_argument("--temperature", type=float, default=0.7, help="Inference temperature (default: 0.7)")

    profile_switch_parser = profile_sub.add_parser("switch", help="Switch to a profile")
    profile_switch_parser.add_argument("identifier", help="Profile ID or name")

    profile_show_parser = profile_sub.add_parser("show", help="Show profile details")
    profile_show_parser.add_argument("identifier", nargs="?", help="Profile ID or name (omit for active profile)")

    profile_delete_parser = profile_sub.add_parser("delete", help="Delete a profile")
    profile_delete_parser.add_argument("identifier", help="Profile ID or name")
    profile_delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    profile_export_parser = profile_sub.add_parser("export", help="Export a profile to JSON")
    profile_export_parser.add_argument("identifier", help="Profile ID or name")
    profile_export_parser.add_argument("--include-memories", "-m", action="store_true", help="Include profile-scoped memories")
    profile_export_parser.add_argument("--output", "-o", help="Output file path")

    profile_import_parser = profile_sub.add_parser("import", help="Import a profile from JSON")
    profile_import_parser.add_argument("file", help="JSON file to import")

    profile_sub.add_parser("clear", help="Clear the active profile")

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
    elif args.command == "embeddings":
        return cmd_embeddings(args)
    elif args.command == "search":
        return cmd_search(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "init":
        return cmd_init(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "style":
        return cmd_style(args)
    elif args.command == "memory-type":
        return cmd_memory_type(args)
    elif args.command == "profile":
        return cmd_profile(args)
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
    from threadlight.memory.schemas import CapsuleFilter

    tl = Threadlight(enable_memory=True)

    if args.memory_command == "list":
        # Build filter based on arguments
        model_filter = getattr(args, 'model', None)
        no_shared = getattr(args, 'no_shared', False)
        include_shared = not no_shared

        if model_filter:
            if model_filter.lower() == 'shared':
                # Show only shared memories
                filter_obj = CapsuleFilter(model_scope=None, include_shared=True)
                capsules = tl.memory.list(limit=50, filter=filter_obj)
                # Filter to only shared (model_scope is None)
                capsules = [c for c in capsules if c.model_scope is None]
            else:
                filter_obj = CapsuleFilter(model_scope=model_filter, include_shared=include_shared)
                capsules = tl.memory.list(limit=50, filter=filter_obj)
        else:
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

    elif args.memory_command == "scope":
        scope_cmd = getattr(args, 'scope_command', None)

        if scope_cmd == "status":
            enabled = tl.config.memory.per_model_isolation
            default_shared = tl.config.memory.default_shared
            current_model = tl.config.current_model

            console.print("[bold]Per-Model Memory Isolation Status[/bold]")
            console.print(f"  Enabled: {'Yes' if enabled else 'No'}")
            console.print(f"  Default shared: {'Yes' if default_shared else 'No'}")
            console.print(f"  Current model: {current_model or 'Not set'}")

        elif scope_cmd == "stats":
            if hasattr(tl.storage, 'count_capsules_by_model'):
                counts = tl.storage.count_capsules_by_model()
            else:
                counts = {}

            console.print("[bold]Memory Counts by Model[/bold]")
            shared_count = counts.get(None, 0)
            console.print(f"  Shared (all models): {shared_count}")

            for model, count in sorted(counts.items()):
                if model is not None:
                    console.print(f"  {model}: {count}")

            total = sum(counts.values())
            console.print(f"\n  Total: {total}")

        elif scope_cmd == "enable":
            default_shared = getattr(args, 'default_shared', False)
            tl.set_per_model_isolation(True)
            if default_shared:
                tl.set_default_shared(True)
            console.print("[success]Per-model memory isolation enabled[/success]")
            if default_shared:
                console.print("  New memories will be shared by default")
            else:
                console.print("  New memories will be scoped to the current model")

        elif scope_cmd == "disable":
            tl.set_per_model_isolation(False)
            console.print("[success]Per-model memory isolation disabled[/success]")
            console.print("  All memories are now accessible by all models")

        elif scope_cmd == "share":
            capsule_id = args.capsule_id
            success = tl.share_memory(capsule_id)
            if success:
                console.print(f"[success]Memory {capsule_id} is now shared across all models[/success]")
            else:
                console.print(f"[error]Failed to share memory {capsule_id}[/error]")
                tl.close()
                return 1

        elif scope_cmd == "assign":
            capsule_id = args.capsule_id
            model = getattr(args, 'model', None) or tl.config.current_model
            if not model:
                console.print("[error]No model specified and no current model set[/error]")
                console.print("  Use --model to specify the target model")
                tl.close()
                return 1
            success = tl.assign_memory_to_model(capsule_id, model)
            if success:
                console.print(f"[success]Memory {capsule_id} assigned to model {model}[/success]")
            else:
                console.print(f"[error]Failed to assign memory {capsule_id} to {model}[/error]")
                tl.close()
                return 1

        else:
            console.print("Use 'threadlight memory scope --help' for commands")

    else:
        console.print("Use 'threadlight memory --help' for commands")

    tl.close()
    return 0


def cmd_embeddings(args: argparse.Namespace) -> int:
    """Embedding management commands."""
    from threadlight import Threadlight

    tl = Threadlight(enable_memory=True)

    if args.embeddings_command == "generate":
        if not tl.config.memory.embeddings.enabled:
            console.print("[error]Embeddings not enabled.[/error]")
            console.print("[dim]Run 'threadlight embeddings enable' first.[/dim]")
            tl.close()
            return 1

        include_memories = not getattr(args, 'conversations_only', False)
        include_conversations = not getattr(args, 'memories_only', False)

        console.print("[bold]Generating embeddings...[/bold]")
        console.print(f"  Provider: {tl.config.memory.embeddings.provider}")
        console.print(f"  Model: {tl.config.memory.embeddings.model}")
        console.print(f"  Memories: {include_memories}")
        console.print(f"  Conversations: {include_conversations}")
        console.print()

        # Progress callback
        last_update = [0, 0]  # [capsules, messages]

        def progress_callback(stats):
            if stats.capsules_updated - last_update[0] >= 50 or stats.messages_updated - last_update[1] >= 100:
                console.print(
                    f"  [dim]Progress: {stats.capsules_updated} capsules, "
                    f"{stats.messages_updated} messages[/dim]"
                )
                last_update[0] = stats.capsules_updated
                last_update[1] = stats.messages_updated

        with console.status("[dim]Generating embeddings (this may take a while)...[/dim]", spinner="dots"):
            try:
                stats = tl.generate_embeddings(
                    include_memories=include_memories,
                    include_messages=include_conversations,
                )
            except Exception as e:
                console.print(f"[error]Failed to generate embeddings: {e}[/error]")
                tl.close()
                return 1

        console.print("\n[bold green]Embedding generation complete![/bold green]")
        console.print(f"  Capsules processed: {stats.capsules_processed}")
        console.print(f"  Capsules updated: {stats.capsules_updated}")
        console.print(f"  Messages processed: {stats.messages_processed}")
        console.print(f"  Messages updated: {stats.messages_updated}")
        if stats.errors > 0:
            console.print(f"  [yellow]Errors: {stats.errors}[/yellow]")
        console.print(f"  Duration: {stats.duration_seconds:.1f}s")

    elif args.embeddings_command == "stats":
        if not tl.config.memory.embeddings.enabled:
            console.print("[dim]Embeddings not enabled.[/dim]")
            console.print("[dim]Run 'threadlight embeddings enable' to enable.[/dim]")
            tl.close()
            return 0

        try:
            stats = tl.get_embedding_stats()
        except Exception as e:
            console.print(f"[error]Failed to get stats: {e}[/error]")
            tl.close()
            return 1

        console.print("\n[bold]Embedding Statistics[/bold]")
        console.print(f"  Provider: {stats.get('provider', 'unknown')}")
        console.print(f"  Dimension: {stats.get('dimension', 'unknown')}")

        capsules = stats.get("capsules", {})
        console.print(f"\n[bold]Memory Capsules:[/bold]")
        console.print(f"  Total: {capsules.get('total', 0)}")
        console.print(f"  With embeddings: {capsules.get('with_embeddings', 0)}")
        coverage = capsules.get('coverage', 0)
        coverage_color = "green" if coverage >= 0.9 else "yellow" if coverage >= 0.5 else "red"
        console.print(f"  Coverage: [{coverage_color}]{coverage*100:.1f}%[/{coverage_color}]")

        messages = stats.get("messages", {})
        console.print(f"\n[bold]Messages:[/bold]")
        console.print(f"  Total: {messages.get('total', 0)}")
        console.print(f"  With embeddings: {messages.get('with_embeddings', 0)}")
        msg_coverage = messages.get('coverage', 0)
        msg_coverage_color = "green" if msg_coverage >= 0.9 else "yellow" if msg_coverage >= 0.5 else "red"
        console.print(f"  Coverage: [{msg_coverage_color}]{msg_coverage*100:.1f}%[/{msg_coverage_color}]")

    elif args.embeddings_command == "enable":
        provider = getattr(args, 'provider', 'local')
        model = getattr(args, 'model', 'intfloat/e5-small-v2')

        tl.config.memory.embeddings.enabled = True
        tl.config.memory.embeddings.provider = provider
        tl.config.memory.embeddings.model = model
        tl.save_config()

        console.print("[success]Embeddings enabled![/success]")
        console.print(f"  Provider: {provider}")
        console.print(f"  Model: {model}")
        console.print("\n[dim]Run 'threadlight embeddings generate' to generate embeddings.[/dim]")

    elif args.embeddings_command == "disable":
        tl.config.memory.embeddings.enabled = False
        tl.save_config()
        console.print("[success]Embeddings disabled.[/success]")

    else:
        console.print("Use 'threadlight embeddings --help' for commands")

    tl.close()
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search memories and conversations."""
    from threadlight import Threadlight

    tl = Threadlight(enable_memory=True)

    query = args.query
    limit = getattr(args, 'limit', 10)
    use_semantic = getattr(args, 'semantic', False)
    memories_only = getattr(args, 'memories_only', False)
    conversations_only = getattr(args, 'conversations_only', False)
    threshold = getattr(args, 'threshold', 0.5)

    if use_semantic:
        if not tl.config.memory.embeddings.enabled:
            console.print("[error]Semantic search requires embeddings.[/error]")
            console.print("[dim]Run 'threadlight embeddings enable' and 'threadlight embeddings generate' first.[/dim]")
            tl.close()
            return 1

        console.print(f"[bold]Semantic search for:[/bold] {query}")
        console.print(f"[dim]Threshold: {threshold}, Limit: {limit}[/dim]\n")

        results = []

        with console.status("[dim]Searching...[/dim]", spinner="dots"):
            try:
                if not conversations_only:
                    memory_results = tl.search_memories_semantic(
                        query=query,
                        limit=limit,
                        threshold=threshold,
                    )
                    results.extend(memory_results)

                if not memories_only:
                    conv_results = tl.search_conversations_semantic(
                        query=query,
                        limit=limit,
                        threshold=threshold,
                    )
                    results.extend(conv_results)

            except Exception as e:
                console.print(f"[error]Search failed: {e}[/error]")
                tl.close()
                return 1

        # Sort and limit results
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        results = results[:limit]

        if not results:
            console.print("[dim]No results found.[/dim]")
            tl.close()
            return 0

        console.print(f"[bold]Results ({len(results)} found):[/bold]\n")

        table = Table(border_style="dim")
        table.add_column("Type", style="cyan", width=10)
        table.add_column("Score", style="green", width=8)
        table.add_column("Content", style="white", overflow="ellipsis")
        table.add_column("Source", style="dim", width=20)

        for result in results:
            result_dict = result.to_dict()
            result_type = result_dict.get("type", "unknown")

            if result_type == "capsule":
                content = result_dict.get("content", {})
                # Try to get a preview
                preview = ""
                if "seed" in content:
                    preview = content.get("content", {}).get("seed", "")[:60]
                elif "entity" in content:
                    preview = f"{content.get('content', {}).get('entity', '')}: {content.get('content', {}).get('summary', '')[:40]}"
                elif "name" in content:
                    preview = f"{content.get('content', {}).get('name', '')}: {content.get('content', {}).get('description', '')[:40]}"
                else:
                    preview = str(content.get("content", {}))[:60]
                source = f"capsule:{result_dict.get('capsule_type', '')}"
            else:
                preview = result_dict.get("content", "")[:60]
                source = result_dict.get("conversation_name", "")[:20] or "[conversation]"

            similarity = result_dict.get("similarity_score", 0)

            table.add_row(
                result_type,
                f"{similarity:.2f}",
                preview + ("..." if len(preview) == 60 else ""),
                source,
            )

        console.print(table)

    else:
        # Keyword search (existing functionality)
        console.print(f"[bold]Keyword search for:[/bold] {query}\n")

        with console.status("[dim]Searching...[/dim]", spinner="dots"):
            if not conversations_only:
                capsules = tl.recall(query, limit=limit)
                if capsules:
                    format_memory_table(capsules, f"Memories matching '{query}'")

            if not memories_only:
                results = tl.search_conversations(query, limit=limit)
                if results:
                    console.print(f"\n[bold]Conversations matching '{query}':[/bold]\n")

                    table = Table(border_style="dim")
                    table.add_column("Conversation", style="white", width=20)
                    table.add_column("Role", style="cyan", width=10)
                    table.add_column("Content", style="white", overflow="ellipsis")

                    for result in results:
                        msg = result.message
                        conv_name = result.conversation_name or "[unnamed]"
                        if len(conv_name) > 20:
                            conv_name = conv_name[:17] + "..."

                        role_label = "You" if msg.role == "user" else "Assistant"
                        content = msg.content[:60] + ("..." if len(msg.content) > 60 else "")

                        table.add_row(conv_name, role_label, content)

                    console.print(table)

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
            "system_prompt": ""
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

        # Check if using freeform mode
        freeform_description = getattr(args, 'freeform_description', None)
        use_freeform = bool(freeform_description)

        profile = tl.create_style_profile(
            style_id=args.name,
            tone_base=args.tone if not use_freeform else "",
            permissions=args.permissions or [],
            constraints=args.constraints or [],
            freeform_description=freeform_description or "",
            use_freeform=use_freeform,
        )
        tl.save_style_profile(profile)

        if use_freeform:
            console.print(f"[success]Created freeform style profile: {args.name}[/success]")
        else:
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

            # Check if freeform style
            if profile.use_freeform and profile.freeform_description:
                console.print("[dim]Type: Freeform[/dim]\n")
                console.print("[bold]Style Definition:[/bold]")
                console.print(profile.freeform_description)
            else:
                console.print("[dim]Type: Structured[/dim]\n")
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


def cmd_memory_type(args: argparse.Namespace) -> int:
    """Custom memory type management commands."""
    from threadlight import Threadlight
    from threadlight.capsules import (
        FieldDefinition,
        CustomTypeDefinition,
        EXAMPLE_TYPES,
        list_example_types,
        get_example_type,
    )

    if args.memory_type_command == "list":
        tl = Threadlight(enable_memory=True)
        types = tl.list_memory_types(include_builtin=False)

        console.print("\n[bold]Custom Memory Types[/bold]\n")

        if not types:
            console.print("[dim]No custom memory types defined.[/dim]")
            console.print("\nCreate one with: threadlight memory-type create <type_id>")
            console.print("Or import an example: threadlight memory-type import <example_id>")
        else:
            table = Table(border_style="dim")
            table.add_column("Type ID", style="cyan")
            table.add_column("Fields", style="white")
            table.add_column("Description", style="dim")

            for t in types:
                fields = t.get("fields", [])
                field_names = [f.get("name", "") for f in fields]
                table.add_row(
                    t.get("type_id", ""),
                    ", ".join(field_names[:5]) + ("..." if len(field_names) > 5 else ""),
                    (t.get("description") or "")[:50],
                )

            console.print(table)

        console.print()
        tl.close()

    elif args.memory_type_command == "create":
        tl = Threadlight(enable_memory=True)

        # Check if type already exists
        existing = tl.get_memory_type(args.type_id)
        if existing:
            console.print(f"[error]Memory type already exists: {args.type_id}[/error]")
            tl.close()
            return 1

        # Parse fields
        fields = []
        for field_str in args.fields or []:
            parts = field_str.split(":")
            if len(parts) < 2:
                console.print(f"[error]Invalid field format: {field_str}[/error]")
                console.print("Expected format: name:type[:required]")
                tl.close()
                return 1

            name = parts[0]
            field_type = parts[1]
            required = len(parts) > 2 and parts[2].lower() == "required"

            if field_type not in ("string", "text", "number", "date", "list"):
                console.print(f"[error]Invalid field type: {field_type}[/error]")
                console.print("Valid types: string, text, number, date, list")
                tl.close()
                return 1

            fields.append({
                "name": name,
                "type": field_type,
                "required": required,
            })

        if not fields:
            console.print("[error]At least one field is required[/error]")
            console.print("Use: --field name:type[:required]")
            tl.close()
            return 1

        # Generate display name from type_id
        display_name = args.name if args.name else args.type_id.replace("_", " ").title()

        # Create type definition
        type_def = tl.create_memory_type(
            type_id=args.type_id,
            display_name=display_name,
            fields=fields,
            description=args.description or "",
            display_template=args.template or "",
        )

        console.print(f"[success]Created memory type: {args.type_id}[/success]")
        console.print(f"  Fields: {', '.join(f['name'] for f in fields)}")
        if args.template:
            console.print(f"  Display template: {args.template}")

        tl.close()

    elif args.memory_type_command == "show":
        tl = Threadlight(enable_memory=True)

        type_def = tl.get_memory_type(args.type_id)
        if not type_def:
            console.print(f"[error]Memory type not found: {args.type_id}[/error]")
            tl.close()
            return 1

        console.print(f"\n[bold]Memory Type: {type_def.get('type_id', '')}[/bold]\n")

        description = type_def.get("description")
        if description:
            console.print(f"[dim]{description}[/dim]\n")

        console.print("[bold]Fields:[/bold]")
        for field in type_def.get("fields", []):
            required = field.get("required", False)
            req_mark = " [yellow](required)[/yellow]" if required else ""
            desc = f" - {field.get('description', '')}" if field.get("description") else ""
            field_type = field.get("field_type") or field.get("type", "string")
            console.print(f"  {field.get('name', '')}: {field_type}{req_mark}{desc}")

        display_template = type_def.get("display_template")
        if display_template:
            console.print(f"\n[bold]Display Template:[/bold] {display_template}")

        console.print()
        tl.close()

    elif args.memory_type_command == "delete":
        tl = Threadlight(enable_memory=True)

        type_def = tl.get_memory_type(args.type_id)
        if not type_def:
            console.print(f"[error]Memory type not found: {args.type_id}[/error]")
            tl.close()
            return 1

        if not args.force:
            console.print(f"[warning]This will delete memory type '{args.type_id}'[/warning]")
            console.print("Existing memories of this type will become orphaned.")
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                console.print("[dim]Cancelled.[/dim]")
                tl.close()
                return 0

        success = tl.delete_memory_type(args.type_id)
        if success:
            console.print(f"[success]Deleted memory type: {args.type_id}[/success]")
        else:
            console.print(f"[error]Failed to delete memory type: {args.type_id}[/error]")
            tl.close()
            return 1

        tl.close()

    elif args.memory_type_command == "examples":
        console.print("\n[bold]Example Memory Types[/bold]\n")
        console.print("[dim]These are pre-defined type templates you can import.[/dim]\n")

        table = Table(border_style="dim")
        table.add_column("ID", style="cyan")
        table.add_column("Fields", style="white")
        table.add_column("Description", style="dim")

        for type_id in list_example_types():
            example = get_example_type(type_id)
            if example:
                field_names = [f.name for f in example.fields]
                table.add_row(
                    type_id,
                    ", ".join(field_names[:4]) + ("..." if len(field_names) > 4 else ""),
                    (example.description or "")[:40],
                )

        console.print(table)
        console.print("\nImport with: threadlight memory-type import <example_id>")
        console.print()

    elif args.memory_type_command == "import":
        tl = Threadlight(enable_memory=True)

        # Check if already exists
        existing = tl.get_memory_type(args.type_id)
        if existing:
            console.print(f"[error]Memory type already exists: {args.type_id}[/error]")
            tl.close()
            return 1

        type_def = tl.import_example_type(args.type_id)
        if not type_def:
            console.print(f"[error]Example type not found: {args.type_id}[/error]")
            console.print("Use 'threadlight memory-type examples' to see available examples.")
            tl.close()
            return 1

        console.print(f"[success]Imported memory type: {args.type_id}[/success]")
        console.print(f"  Fields: {', '.join(f.name for f in type_def.fields)}")

        tl.close()

    else:
        console.print("Use 'threadlight memory-type --help' for commands")

    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Profile management commands."""
    from threadlight import Threadlight
    import json

    if args.profile_command == "list":
        tl = Threadlight(enable_memory=True)
        profiles = tl.list_profiles()
        active = tl.get_active_profile()

        if not profiles:
            console.print("\n[dim]No profiles found. Create one with:[/dim]")
            console.print("  threadlight profile create <name>\n")
            tl.close()
            return 0

        console.print("\n[bold]Profiles[/bold]\n")

        table = Table(border_style="dim")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Name", style="white")
        table.add_column("Model", style="cyan", width=30)
        table.add_column("Style", style="magenta", width=12)
        table.add_column("Updated", style="dim", width=16)

        for p in profiles:
            pid = p.id[:8] + "..."
            name = p.name
            if active and p.id == active.id:
                name = f"[green]* {name}[/green]"

            model = p.primary_model
            if len(model) > 30:
                model = model[:27] + "..."

            style = p.style_profile_id or "-"
            updated = p.updated_at.strftime("%Y-%m-%d %H:%M")

            table.add_row(pid, name, model, style, updated)

        console.print(table)
        console.print("\n[dim]* = active profile[/dim]\n")
        tl.close()

    elif args.profile_command == "create":
        tl = Threadlight(enable_memory=True)

        model = args.model or tl.config.provider.model
        profile = tl.create_profile(
            name=args.name,
            description=args.description,
            primary_model=model,
            system_prompt=args.system_prompt or "",
            style_profile_id=args.style,
            color=args.color,
            temperature=args.temperature,
        )

        console.print(f"\n[success]Created profile: {profile.name}[/success]")
        console.print(f"  ID: {profile.id}")
        console.print(f"  Model: {profile.primary_model}")
        console.print("\nSwitch to it with:")
        console.print(f"  threadlight profile switch {profile.id[:8]}\n")
        tl.close()

    elif args.profile_command == "switch":
        tl = Threadlight(enable_memory=True)

        # Find by ID or name
        profiles = tl.list_profiles()
        match = None
        identifier = args.identifier

        for p in profiles:
            if p.id.startswith(identifier) or p.name.lower() == identifier.lower():
                match = p
                break

        if not match:
            console.print(f"[error]Profile not found: {identifier}[/error]")
            tl.close()
            return 1

        tl.switch_profile(match.id)
        console.print(f"\n[success]Switched to profile: {match.name}[/success]")
        console.print(f"  Model: {match.primary_model}")
        if match.style_profile_id:
            console.print(f"  Style: {match.style_profile_id}")
        console.print()
        tl.close()

    elif args.profile_command == "show":
        tl = Threadlight(enable_memory=True)

        if args.identifier:
            # Find by ID or name
            profiles = tl.list_profiles()
            profile = None
            for p in profiles:
                if p.id.startswith(args.identifier) or p.name.lower() == args.identifier.lower():
                    profile = p
                    break
            if not profile:
                console.print(f"[error]Profile not found: {args.identifier}[/error]")
                tl.close()
                return 1
        else:
            profile = tl.get_active_profile()
            if not profile:
                console.print("[dim]No active profile. Use /profile show <id> to view one.[/dim]")
                tl.close()
                return 0

        active = tl.get_active_profile()
        is_active = active and profile.id == active.id

        console.print(f"\n[bold]Profile: {profile.name}[/bold]")
        if is_active:
            console.print("[green](active)[/green]")

        console.print(f"\n[dim]ID:[/dim] {profile.id}")
        console.print(f"[dim]Description:[/dim] {profile.description or '[none]'}")
        console.print(f"[dim]Model:[/dim] {profile.primary_model}")
        console.print(f"[dim]Temperature:[/dim] {profile.temperature}")
        console.print(f"[dim]Style:[/dim] {profile.style_profile_id or '[none]'}")
        console.print(f"[dim]Memory Scope:[/dim] {profile.memory_scope}")
        console.print(f"[dim]Access Shared:[/dim] {profile.access_shared_memories}")
        console.print(f"[dim]Color:[/dim] {profile.color or '[none]'}")
        console.print(f"[dim]Created:[/dim] {profile.created_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"[dim]Updated:[/dim] {profile.updated_at.strftime('%Y-%m-%d %H:%M')}")

        if profile.system_prompt:
            console.print("\n[dim]System Prompt:[/dim]")
            prompt = profile.system_prompt
            if len(prompt) > 300:
                prompt = prompt[:300] + "..."
            console.print(f"  {prompt}")

        console.print()
        tl.close()

    elif args.profile_command == "delete":
        tl = Threadlight(enable_memory=True)

        # Find by ID or name
        profiles = tl.list_profiles()
        profile = None
        for p in profiles:
            if p.id.startswith(args.identifier) or p.name.lower() == args.identifier.lower():
                profile = p
                break

        if not profile:
            console.print(f"[error]Profile not found: {args.identifier}[/error]")
            tl.close()
            return 1

        if not args.force:
            console.print(f"[warning]This will delete profile '{profile.name}'[/warning]")
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                console.print("[dim]Cancelled.[/dim]")
                tl.close()
                return 0

        success = tl.delete_profile(profile.id)
        if success:
            console.print(f"[success]Deleted profile: {profile.name}[/success]")
        else:
            console.print(f"[error]Failed to delete profile[/error]")
            tl.close()
            return 1

        tl.close()

    elif args.profile_command == "export":
        tl = Threadlight(enable_memory=True)

        # Find by ID or name
        profiles = tl.list_profiles()
        profile = None
        for p in profiles:
            if p.id.startswith(args.identifier) or p.name.lower() == args.identifier.lower():
                profile = p
                break

        if not profile:
            console.print(f"[error]Profile not found: {args.identifier}[/error]")
            tl.close()
            return 1

        export_data = tl.export_profile(
            profile.id,
            include_memories=args.include_memories,
        )

        # Determine output file
        if args.output:
            filename = args.output
        else:
            safe_name = profile.name.lower().replace(' ', '_').replace('/', '_')
            filename = f"profile_{safe_name}_{profile.id[:8]}.json"

        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)

        console.print(f"\n[success]Exported profile to: {filename}[/success]")
        if args.include_memories:
            mem_count = len(export_data.get('memories', []))
            console.print(f"[dim]Included {mem_count} memories[/dim]")
        console.print()
        tl.close()

    elif args.profile_command == "import":
        tl = Threadlight(enable_memory=True)

        try:
            with open(args.file, 'r') as f:
                export_data = json.load(f)
        except FileNotFoundError:
            console.print(f"[error]File not found: {args.file}[/error]")
            tl.close()
            return 1
        except json.JSONDecodeError:
            console.print(f"[error]Invalid JSON file: {args.file}[/error]")
            tl.close()
            return 1

        profile = tl.import_profile(export_data)
        console.print(f"\n[success]Imported profile: {profile.name}[/success]")
        console.print(f"  ID: {profile.id}")
        console.print("\nSwitch to it with:")
        console.print(f"  threadlight profile switch {profile.id[:8]}\n")
        tl.close()

    elif args.profile_command == "clear":
        tl = Threadlight(enable_memory=True)
        active = tl.get_active_profile()

        if not active:
            console.print("[dim]No active profile to clear.[/dim]")
            tl.close()
            return 0

        tl.clear_profile()
        console.print("[success]Cleared active profile. Using default settings.[/success]")
        tl.close()

    else:
        console.print("Use 'threadlight profile --help' for commands")

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
