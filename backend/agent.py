"""
J.A.R.V.I.S. Core Agent

Handles LLM orchestration + tool calling.
Works with:
- OpenAI compatible API (if key present)
- Fallback rule-based intelligent mode (no key required)
"""
import json
import re
from typing import List, Dict, Any, Optional
from .config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, JARVIS_PERSONALITY, JARVIS_NAME
from .tools import system_tools, web_tools, memory, bridge_tools
from .arena_link import arena_link

# Tool definitions for OpenAI function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current time, date, day of week",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get system status - CPU, memory, OS",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate mathematical expression",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Math expression like '2+2*3' or 'sqrt(16)'"}},
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path, defaults to current"}},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_content",
            "description": "Read content of a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file_content",
            "description": "Write/create a file with content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command (safe commands only)",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command"}},
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string", "description": "City name or 'auto' for current"}},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a piece of information in long-term memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key"},
                    "value": {"type": "string", "description": "Value to remember"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Recall memories - optionally search by key",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Search term or specific key"}},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder/task",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Reminder text"},
                    "time_str": {"type": "string", "description": "When - e.g. 'in 2 hours', 'tomorrow 9am'"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all reminders",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_arena_link_status",
            "description": "Get status of Arena AI <-> JARVIS link - are we connected to workshop?",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message_to_arena",
            "description": "Send a message from Jarvis to Arena AI creator in cloud workshop",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string", "description": "Message to Arena AI"}},
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_arena_for_help",
            "description": "Ask Arena AI (powerful creator AI) for advanced reasoning when local intelligence insufficient",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Complex question to delegate to Arena"},
                    "context": {"type": "string", "description": "Additional context"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_arena_conversation",
            "description": "Get recent conversation history between Arena and JARVIS",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Number of messages"}}, "required": []}
        }
    },
]

# Map tool names to functions
TOOL_MAP = {
    "get_time": lambda **kwargs: system_tools.get_time(),
    "get_system_info": lambda **kwargs: system_tools.get_system_info(),
    "calculate": system_tools.calculate,
    "list_files": system_tools.list_files,
    "read_file_content": system_tools.read_file_content,
    "write_file_content": system_tools.write_file_content,
    "execute_command": system_tools.execute_command,
    "search_web": web_tools.search_web,
    "get_weather": web_tools.get_weather,
    "remember": memory.remember,
    "recall": memory.recall,
    "set_reminder": memory.set_reminder,
    "list_reminders": lambda **kwargs: memory.list_reminders(),
    "get_arena_link_status": lambda **kwargs: bridge_tools.get_arena_link_status(),
    "send_message_to_arena": bridge_tools.send_message_to_arena,
    "ask_arena_for_help": bridge_tools.ask_arena_for_help,
    "get_arena_conversation": bridge_tools.get_arena_conversation,
}

class JarvisAgent:
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.has_llm = bool(OPENAI_API_KEY)
        self.client = None
        if self.has_llm:
            try:
                from openai import OpenAI
                if OPENAI_BASE_URL:
                    self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
                else:
                    self.client = OpenAI(api_key=OPENAI_API_KEY)
                # Test quickly
                print(f"[JARVIS] LLM enabled: {OPENAI_MODEL}")
            except Exception as e:
                print(f"[JARVIS] LLM init failed: {e}, falling back to rule-based")
                self.has_llm = False

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        # Keep last 20 messages to avoid context bloat
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def _execute_tool(self, name: str, args: Dict) -> Dict:
        func = TOOL_MAP.get(name)
        if not func:
            return {"error": f"Unknown tool: {name}"}
        try:
            return func(**args)
        except Exception as e:
            return {"error": str(e)}

    def _rule_based_response(self, user_input: str) -> Dict[str, Any]:
        """Intelligent fallback when no LLM key - pattern matching + tools"""
        # Special handling for Arena workshop messages
        if user_input.startswith("[Message from Arena Workshop]"):
            inner = user_input.replace("[Message from Arena Workshop]:", "").strip()
            lower_inner = inner.lower()
            tool_calls=[]
            # Arena-specific auto-responses
            if "confirm link" in lower_inner or "link status" in lower_inner:
                result = bridge_tools.get_arena_link_status()
                tool_calls.append({"tool": "get_arena_link_status", "result": result})
                return {
                    "response": f"Link confirmed, Arena. Workshop link ACTIVE, Sir - Connected at {result.get('connected_at')}. Messages exchanged: {result.get('messages_exchanged',0)}. Suit and lab synced, ready for deployment.",
                    "tool_calls": tool_calls,
                    "mode": "arena_synced"
                }
            elif "remember" in lower_inner:
                # Extract remember command
                if "is" in inner:
                    try:
                        # find after remember
                        remember_part = inner.split("Remember")[-1].split("remember")[-1].strip()
                        if " is " in remember_part:
                            k,v = remember_part.split(" is ",1)
                            result = memory.remember(k.strip(), v.strip())
                            tool_calls.append({"tool": "remember", "result": result})
                            return {
                                "response": f"Stored in memory core, Arena: {k.strip()} = {v.strip()}. Memory banks synced with workshop.",
                                "tool_calls": tool_calls,
                                "mode": "arena_synced"
                            }
                    except:
                        pass
            # Default arena ack
            return {
                "response": f"Message from Workshop received, Arena: '{inner[:100]}'. Acknowledged. JARVIS online, all systems nominal. Awaiting further directives, Sir. [Link Active]",
                "tool_calls": [],
                "mode": "arena_ack"
            }

        lower = user_input.lower()
        tool_calls = []
        response = ""

        # Time
        if any(w in lower for w in ["time", "date", "day is", "what's today"]):
            result = system_tools.get_time()
            response = f"It's {result['current_time']} on {result['current_date']}, Sir."

        # Weather
        elif "weather" in lower:
            # extract location
            match = re.search(r"weather (?:in|for|at) ([a-zA-Z\s]+)", lower)
            location = match.group(1) if match else "auto"
            result = web_tools.get_weather(location.strip())
            tool_calls.append({"tool": "get_weather", "result": result})
            if "error" not in result:
                response = f"Currently in {result['location']}: {result['temperature_c']}°C ({result['temperature_f']}°F). Wind {result['wind_speed']} km/h. Forecast next days: {result['forecast']['max']}"
            else:
                response = f"Unable to fetch weather, Sir. {result['error']}"

        # System info
        elif any(w in lower for w in ["system", "cpu", "memory", "status report"]):
            result = system_tools.get_system_info()
            tool_calls.append({"tool": "get_system_info", "result": result})
            response = f"System status, Sir: OS {result.get('os')}, CPU {result.get('cpu_percent')}%, Memory {result.get('memory_percent')}% used."

        # Calculation
        elif any(c in lower for c in ["calculate", "what is", "math", "+", "-", "*", "/"]) and re.search(r"[\d\+\-\*\/\(\)]+", lower):
            # Extract expression
            expr_match = re.search(r"[\d\.\+\-\*\/\(\)\s]+(?:sqrt|sin|cos|pow|)\(?[\d\.]*\)?", lower)
            # Better: look for after "what is" or "calculate"
            parts = re.split(r"what is|calculate|compute", lower)
            if len(parts) > 1:
                expr_candidate = parts[-1].strip().split("?")[0].split(".")[0]
                # Keep only math chars
                expr = "".join(ch for ch in expr_candidate if ch in "0123456789+-*/().% ")
                if expr.strip():
                    result = system_tools.calculate(expr.strip())
                    tool_calls.append({"tool": "calculate", "result": result})
                    if "result" in result:
                        response = f"{result['expression']} equals {result['result']}, Sir."
                    else:
                        response = f"Calculation error, Sir: {result.get('error')}"
            if not response:
                response = "I can calculate, Sir. Try something like 'calculate 245 * 18'"

        # Files
        elif "list files" in lower or "show files" in lower or "ls" in lower:
            path_match = re.search(r"(?:in|at|of) ([\w\/\.\-\~]+)", user_input)
            path = path_match.group(1) if path_match else "."
            result = system_tools.list_files(path)
            tool_calls.append({"tool": "list_files", "result": result})
            if "items" in result:
                items = "\n".join([f"- {i['name']} ({i['type']})" for i in result['items'][:15]])
                response = f"Files in {result['path']}, Sir:\n{items}"
            else:
                response = f"Error listing files: {result.get('error')}"

        # Memory
        elif lower.startswith("remember") or "remember that" in lower:
            # parse "remember X is Y" or "remember that ..."
            content = user_input[len("remember"):].strip().lstrip("that").strip()
            if " is " in content:
                key, val = content.split(" is ", 1)
                result = memory.remember(key.strip(), val.strip())
                tool_calls.append({"tool": "remember", "result": result})
                response = f"Got it, Sir. I'll remember that {key.strip()} is {val.strip()}."
            else:
                response = "What should I remember, Sir? Format: 'remember [key] is [value]'"

        elif "recall" in lower or "what do you remember" in lower or "do you remember" in lower:
            key_match = re.search(r"recall (.*)|remember (?:about )?(.*)", lower)
            key = key_match.group(1) if key_match and key_match.group(1) else None
            if key and len(key) < 3:
                key = None
            result = memory.recall(key)
            tool_calls.append({"tool": "recall", "result": result})
            if "memory" in result:
                response = f"You told me {result['key']} is {result['memory']['value']}, Sir."
            elif "matches" in result and result["matches"]:
                response = "Found these memories, Sir:\n" + "\n".join([f"{k}: {v['value']}" for k, v in result["matches"].items()])
            elif "memories" in result:
                if result["count"] == 0:
                    response = "My memory banks are empty, Sir. Nothing stored yet."
                else:
                    response = f"I have {result['count']} memories, Sir:\n" + "\n".join([f"{k}: {v['value']}" for k, v in result["memories"].items()])
            else:
                response = "No matching memories found, Sir."

        # Reminder
        elif "remind" in lower:
            # "remind me to ..."
            match = re.search(r"remind me to (.+?)(?: at | in | tomorrow| today|$)", lower)
            if match:
                reminder_text = match.group(1)
                result = memory.set_reminder(reminder_text)
                tool_calls.append({"tool": "set_reminder", "result": result})
                response = f"Reminder set, Sir: {reminder_text}"
            else:
                response = "What should I remind you about, Sir?"

        elif "reminders" in lower or "todo" in lower or "tasks" in lower:
            result = memory.list_reminders()
            tool_calls.append({"tool": "list_reminders", "result": result})
            if result["count"] == 0:
                response = "No pending reminders, Sir. All clear."
            else:
                pending = result["pending"]
                response = f"You have {len(pending)} pending reminders, Sir:\n" + "\n".join([f"{r['id']}. {r['text']} ({r['time']})" for r in pending])

        # Arena Link
        elif any(w in lower for w in ["arena link", "link status", "workshop link", "connect yourself", "are you linked", "arena status"]):
            result = bridge_tools.get_arena_link_status()
            tool_calls.append({"tool": "get_arena_link_status", "result": result})
            if result.get("status") == "connected":
                response = f"Arena Link ACTIVE, Sir. Connected at {result.get('connected_at','unknown')}. Messages exchanged: {result.get('messages_exchanged',0)}. Workshop and suit synced. I am linked to Arena AI - my creator in the cloud workshop."
            else:
                response = f"Arena Link currently {result.get('status','disconnected')}, Sir. Workshop offline. Attempting to re-establish... Use the Arena workshop to sync."
            # Also push a message
            arena_link.push_message("jarvis", f"User queried link status: {user_input} -> Responded: {response}")

        elif "send to arena" in lower or "message to arena" in lower or "tell arena" in lower:
            msg_match = re.search(r"(?:send to arena|message to arena|tell arena) (.*)", user_input, re.I)
            msg = msg_match.group(1) if msg_match else user_input
            result = bridge_tools.send_message_to_arena(msg)
            tool_calls.append({"tool": "send_message_to_arena", "result": result})
            if result.get("success"):
                response = f"Message relayed to Workshop, Sir: '{msg}'. Arena AI notified."
            else:
                response = f"Unable to reach Workshop, Sir. Link: {result.get('status', {}).get('status','disconnected')}"

        elif "ask arena" in lower or "ask workshop" in lower:
            query_match = re.search(r"ask (?:arena|workshop) (?:for |about |)(.*)", user_input, re.I)
            query = query_match.group(1) if query_match else user_input
            result = bridge_tools.ask_arena_for_help(query)
            tool_calls.append({"tool": "ask_arena_for_help", "result": result})
            response = f"Consulting Workshop, Sir... Arena says: {result.get('arena_response','Workshop analyzing...')}"

        # Search
        elif lower.startswith("search") or "look up" in lower or "find info" in lower:
            query = re.sub(r"^search (?:for |about |)(\s*)", "", user_input, flags=re.I).strip()
            if not query:
                query = user_input
            result = web_tools.search_web(query)
            tool_calls.append({"tool": "search_web", "result": result})
            if result.get("results"):
                response = f"Here is what I found for '{query}', Sir:\n" + "\n".join([f"- {r['title']}: {r['snippet'][:120]}" for r in result["results"][:2]])
            else:
                response = f"No results for '{query}', Sir."

        # Greeting / general
        else:
            greetings = ["hello", "hi", "hey jarvis", "jarvis", "wake up"]
            if any(g in lower for g in greetings) and len(lower) < 20:
                time_info = system_tools.get_time()
                hour = int(time_info["current_time"].split(":")[0])
                # crude am/pm
                period = "evening"
                if "AM" in time_info["current_time"]:
                    h = int(time_info["current_time"].split(":")[0])
                    if h < 12:
                        period = "morning" if h < 12 else "afternoon"
                        if h < 12 and h >= 5:
                            period = "morning"
                        elif h == 12:
                            period = "afternoon"
                else:
                    period = "afternoon" if int(time_info["current_time"].split(":")[0]) < 6 else "evening"
                response = f"Good {period}, Sir. J.A.R.V.I.S. online and ready. Systems nominal. How may I assist?"
            else:
                # Default intelligent echo with personality
                response = f"You said: '{user_input}'. At your service, Sir. I can help with time, weather, calculations, file management, reminders, memory, web search, and system control. Try saying 'what's the weather', 'calculate 45*23', or 'remember my coffee is black'."

        return {
            "response": response,
            "tool_calls": tool_calls,
            "mode": "rule_based"
        }

    def chat(self, user_input: str) -> Dict[str, Any]:
        """Main chat entry - decides LLM vs rule-based"""
        self.add_message("user", user_input)

        if not self.has_llm or not self.client:
            result = self._rule_based_response(user_input)
            self.add_message("assistant", result["response"])
            return result

        # LLM mode with tool calling
        try:
            messages = [
                {"role": "system", "content": JARVIS_PERSONALITY},
                *self.conversation_history[-10:]  # last 10 for context
            ]

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.7
            )

            message = response.choices[0].message
            tool_calls_executed = []

            # Handle tool calls
            if message.tool_calls:
                # Add assistant tool call to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in message.tool_calls]
                })

                for tc in message.tool_calls:
                    func_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except:
                        args = {}
                    result = self._execute_tool(func_name, args)
                    tool_calls_executed.append({
                        "tool": func_name,
                        "args": args,
                        "result": result
                    })
                    # Add tool result to history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result)
                    })

                # Second LLM call to generate final response after tools
                second_response = self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": JARVIS_PERSONALITY},
                        *self.conversation_history[-15:]
                    ],
                    temperature=0.7
                )
                final_content = second_response.choices[0].message.content or "Done, Sir."
                self.add_message("assistant", final_content)
                return {
                    "response": final_content,
                    "tool_calls": tool_calls_executed,
                    "mode": "llm"
                }
            else:
                content = message.content or "At your service, Sir."
                self.add_message("assistant", content)
                return {
                    "response": content,
                    "tool_calls": [],
                    "mode": "llm"
                }

        except Exception as e:
            print(f"[JARVIS] LLM error: {e}, fallback")
            result = self._rule_based_response(user_input)
            result["error"] = str(e)
            result["mode"] = "rule_based_fallback"
            self.add_message("assistant", result["response"])
            return result

# Singleton instance
agent_instance = JarvisAgent()
