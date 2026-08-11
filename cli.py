#!/usr/bin/env python3
"""
JARVIS CLI - Your AI Agent in Terminal
Just A Rather Very Intelligent System
Usage:
  python cli.py chat                    # Interactive chat
  python cli.py run "your task"         # Run a task
  python cli.py tools                   # List tools
  python cli.py server                  # Start web server
  python cli.py memory                  # Show memory
"""

import os
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from agent.config import AgentConfig
from agent.core import JARVISAgent

app = typer.Typer(
    name="jarvis",
    help="JARVIS - Just A Rather Very Intelligent System 🤖",
    add_completion=False
)
console = Console()

def get_agent() -> JARVISAgent:
    config = AgentConfig()
    return JARVISAgent(config)

@app.command(name="chat")
def chat_cmd():
    """Start interactive chat with JARVIS"""
    agent = get_agent()
    
    console.print(Panel.fit(
        f"[bold cyan]🤖 JARVIS - {agent.config.agent_name}[/bold cyan]\n"
        f"[dim]{agent.config.agent_description}[/dim]\n\n"
        f"Model: {agent.config.llm_provider}/{agent.config.llm_model}\n"
        f"Workspace: {agent.config.workspace_dir}\n"
        f"Tools: {len(agent.registry.tools)} available\n\n"
        f"Type [bold]exit[/bold] or [bold]quit[/bold] to leave, [bold]clear[/bold] to clear history, [bold]tools[/bold] to list tools",
        title=f"Welcome to {agent.config.agent_name}",
        border_style="cyan"
    ))
    
    while True:
        try:
            user_input = console.input("\n[bold green]You >[/bold green] ")
            
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[yellow]Goodbye! Sir. JARVIS signing off. 👋[/yellow]")
                break
            if user_input.lower() == "clear":
                agent.clear_history()
                console.print("[dim]History cleared[/dim]")
                continue
            if user_input.lower() == "tools":
                console.print(Panel(agent.get_tools_list(), title="Available Tools"))
                continue
            if not user_input.strip():
                continue
            
            console.print(f"\n[bold cyan]{agent.config.agent_name} >[/bold cyan] ", end="")
            
            with console.status(f"[bold cyan]{agent.config.agent_name} is thinking...[/bold cyan]", spinner="dots"):
                response = agent.run(user_input, verbose=False)
            
            try:
                md = Markdown(response)
                console.print(md)
            except:
                console.print(response)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type exit to quit.[/yellow]")
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            console.print(traceback.format_exc())

@app.command(name="run")
def run_cmd(
    task: str = typer.Argument(..., help="Task description for the agent"),
    verbose: bool = typer.Option(True, "--verbose/--quiet", "-v/-q", help="Verbose output"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream response")
):
    """Run a single task"""
    agent = get_agent()
    
    console.print(Panel(
        f"[bold]Task:[/bold] {task}\n"
        f"[dim]Model: {agent.config.llm_provider}/{agent.config.llm_model} | Max steps: {agent.config.max_steps}[/dim]",
        title=f"🚀 JARVIS Task Runner",
        border_style="green"
    ))
    
    if stream:
        def callback(chunk):
            console.print(chunk, end="")
        result = agent.run(task, stream_callback=callback, verbose=verbose)
        console.print()
    else:
        if verbose:
            result = agent.run(task, verbose=True)
        else:
            with console.status(f"[cyan]{agent.config.agent_name} working...[/cyan]"):
                result = agent.run(task, verbose=False)
        
        console.print("\n" + "="*60)
        console.print(Panel(Markdown(result), title="✅ Result", border_style="green"))

@app.command(name="tools")
def tools_cmd():
    """List all available tools"""
    agent = get_agent()
    tools = agent.registry.list_tools()
    
    console.print(f"\n[bold cyan]🛠️  {agent.config.agent_name} has {len(tools)} tools:[/bold cyan]\n")
    for t in tools:
        console.print(f"[bold]{t.name}[/bold]: {t.description}")
        params = t.parameters.get("properties", {})
        if params:
            console.print(f"  [dim]Args: {', '.join(params.keys())}[/dim]")
        console.print()

@app.command(name="server")
def server_cmd(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind")
):
    """Start web server with chat UI"""
    agent = get_agent()
    console.print(f"[cyan]Starting {agent.config.agent_name} web server at http://{host}:{port}[/cyan]")
    console.print(f"[dim]Open browser to chat with {agent.config.agent_name} via UI[/dim]\n")
    
    try:
        import uvicorn
        from server import app as fastapi_app
        uvicorn.run(fastapi_app, host=host, port=port, reload=False)
    except ImportError:
        console.print("[red]FastAPI/uvicorn not installed. Run: pip install -r requirements.txt[/red]")
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")

@app.command(name="memory")
def memory_cmd(
    action: str = typer.Argument("list", help="list, search <query>, clear"),
    query: str = typer.Argument("", help="Search query if action=search")
):
    """Manage JARVIS's memory"""
    from agent.tools.memory import memory_list, memory_search
    from agent.config import AgentConfig
    config = AgentConfig()
    
    if action == "list":
        result = memory_list(20)
        console.print(Panel(result, title=f"🧠 {config.agent_name} Memory (recent 20)"))
    elif action == "search":
        if not query:
            console.print(f"[red]Please provide search query: jarvis memory search 'your query'[/red]")
            return
        result = memory_search(query)
        console.print(Panel(result, title=f"🔍 Memory search: {query}"))
    elif action == "clear":
        confirm = typer.confirm("Clear all memory?")
        if confirm:
            mem_file = config.memory_file
            if mem_file.exists():
                mem_file.write_text("")
                console.print("[green]Memory cleared[/green]")
            else:
                console.print("[dim]Memory already empty[/dim]")
    else:
        console.print(f"[red]Unknown action {action}. Use list/search/clear[/red]")

@app.command(name="init")
def init_cmd():
    """Initialize JARVIS workspace and config"""
    console.print("[cyan]Initializing JARVIS...[/cyan]")
    
    env_path = Path(".env")
    env_example = Path(".env.example")
    if not env_path.exists() and env_example.exists():
        import shutil
        shutil.copy(env_example, env_path)
        console.print(f"[green]✓ Created .env from .env.example[/green]")
        console.print("[yellow]→ Edit .env and add your API keys![/yellow]")
    elif env_path.exists():
        console.print("[dim].env already exists[/dim]")
    
    workspace = Path("./workspace")
    workspace.mkdir(exist_ok=True)
    (workspace / ".gitkeep").touch(exist_ok=True)
    
    memory_dir = Path("./memory")
    memory_dir.mkdir(exist_ok=True)
    
    console.print(f"[green]✓ Workspace: {workspace.resolve()}[/green]")
    console.print(f"[green]✓ Memory: {memory_dir.resolve()}[/green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Edit .env - add OPENAI_API_KEY")
    console.print("2. Run: python cli.py chat")
    console.print("3. Or: python cli.py run \"your task\"")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        chat_cmd()

if __name__ == "__main__":
    app()
