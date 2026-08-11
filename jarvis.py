#!/usr/bin/env python3
"""
J.A.R.V.I.S. - CLI Entry Point
Usage:
  python jarvis.py              # Interactive text mode
  python jarvis.py --server     # Start web server
  python jarvis.py --voice      # Voice mode (requires mic)
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.agent import agent_instance
from backend.tools import system_tools

def print_banner():
    print(r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    Just A Rather Very Intelligent System
    Stark Industries • Mark XLII
    """)
    print("="*60)
    time_info = system_tools.get_time()
    print(f"  Time: {time_info['current_date']} {time_info['current_time']}")
    print(f"  LLM: {'Enabled ('+os.getenv('OPENAI_MODEL','gpt-4o-mini')+')' if agent_instance.has_llm else 'Local Rule-Based Mode'}")
    print(f"  Mode: {'LLM + Tools' if agent_instance.has_llm else 'Intelligent Local'}")
    print("="*60)
    print("  Tips:")
    print("  - 'weather in London', 'time', 'system status'")
    print("  - 'remember my car is Tesla' / 'recall car'")
    print("  - 'calculate 245*18', 'list files', 'remind me to ...'")
    print("  - Say 'exit' or 'jarvis shutdown' to quit")
    print("="*60 + "\n")

def interactive_mode():
    print_banner()
    print("JARVIS: Good day, Sir. Systems nominal. How may I assist?\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "jarvis shutdown", "shutdown", "bye"]:
                print("\nJARVIS: Shutting down, Sir. Always a pleasure.\n")
                break

            result = agent_instance.chat(user_input)
            print(f"\nJARVIS: {result['response']}")
            if result.get('tool_calls'):
                print("   [Tools used]:", ", ".join([tc['tool'] for tc in result['tool_calls']]))
            print()

        except KeyboardInterrupt:
            print("\n\nJARVIS: Interrupted, Sir. Going offline.\n")
            break
        except Exception as e:
            print(f"\nJARVIS: Apologies, Sir, encountered an error: {e}\n")

def server_mode(port=8000):
    print_banner()
    print(f"Starting J.A.R.V.I.S. Web Server on port {port}...")
    print(f"Open http://localhost:{port} in browser\n")
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. AI Agent")
    parser.add_argument("--server", action="store_true", help="Start web server")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--voice", action="store_true", help="Voice mode (text for now)")

    args = parser.parse_args()

    if args.server:
        server_mode(args.port)
    else:
        interactive_mode()
