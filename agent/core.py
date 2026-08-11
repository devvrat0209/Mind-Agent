import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from .config import AgentConfig
from .prompts import SYSTEM_PROMPT, TOOL_USE_INSTRUCTIONS
from .llm import LLMClient, MockLLMClient
from .tools import get_registry

class AURAAgent:
    """
    AURA - Autonomous Universal Reasoning Agent
    Main agent orchestrator with ReAct loop
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.registry = get_registry()
        
        # Init LLM client (fallback to mock if no keys)
        try:
            llm_cfg = self.config.get_llm_config()
            has_key = bool(llm_cfg.get("api_key") and llm_cfg.get("api_key") != "sk-..." and "dummy" not in str(llm_cfg.get("api_key")))
            if not has_key and self.config.llm_provider in ("openai", "openrouter", "groq", "together"):
                print("⚠️  No API key found, using MOCK mode. Set OPENAI_API_KEY in .env for real LLM.")
                self.llm = MockLLMClient(self.config)
            else:
                self.llm = LLMClient(self.config)
        except Exception as e:
            print(f"⚠️  LLM init failed ({e}), using mock mode")
            self.llm = MockLLMClient(self.config)
        
        self.conversation_history: List[Dict[str, str]] = []
        self.step_count = 0
    
    def _build_system_prompt(self) -> str:
        tools_desc = self.registry.get_prompt_description()
        return SYSTEM_PROMPT.format(
            agent_name=self.config.agent_name,
            agent_description=self.config.agent_description,
            workspace_dir=str(self.config.workspace_dir.resolve()),
            current_date=datetime.now().strftime("%Y-%m-%d %A %H:%M:%S"),
            tools_description=tools_desc
        ) + "\n" + TOOL_USE_INSTRUCTIONS
    
    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from LLM response - supports JSON and OpenAI tool format"""
        text = text.strip()
        
        # Try to find JSON object with "tool" key
        # Pattern 1: {"tool": "name", "arguments": {...}}
        json_pattern = r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}'
        # More robust: find any JSON with tool
        try:
            # Try direct parse if whole text is JSON
            if text.startswith("{") and '"tool"' in text:
                # Balance braces
                obj = json.loads(text)
                if "tool" in obj:
                    return obj
        except:
            pass
        
        # Search for JSON in text
        try:
            # Find first { and last } and try parse iteratively
            start = text.find('{"tool"')
            if start != -1:
                # Find matching closing brace
                brace_count = 0
                for i in range(start, len(text)):
                    if text[i] == '{':
                        brace_count += 1
                    elif text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            candidate = text[start:i+1]
                            try:
                                obj = json.loads(candidate)
                                if "tool" in obj:
                                    return obj
                            except:
                                # Try to fix single quotes
                                try:
                                    candidate_fixed = candidate.replace("'", '"')
                                    obj = json.loads(candidate_fixed)
                                    if "tool" in obj:
                                        return obj
                                except:
                                    pass
                            break
        except Exception:
            pass
        
        # Try regex for simpler cases
        try:
            match = re.search(r'"tool"\s*:\s*"([^"]+)"', text)
            if match:
                tool_name = match.group(1)
                # Extract arguments
                args_match = re.search(r'"arguments"\s*:\s*(\{.*\})', text, re.DOTALL)
                if args_match:
                    args_str = args_match.group(1)
                    # Balance braces for args
                    try:
                        args = json.loads(args_str)
                    except:
                        # Try until valid json
                        for j in range(len(args_str), 0, -1):
                            try:
                                args = json.loads(args_str[:j])
                                break
                            except:
                                continue
                        else:
                            args = {}
                else:
                    args = {}
                return {"tool": tool_name, "arguments": args}
        except:
            pass
        
        return None
    
    def _format_history_for_llm(self) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(self.conversation_history)
        return messages
    
    def run(self, user_input: str, stream_callback: Optional[Callable[[str], None]] = None, verbose: bool = True) -> str:
        """
        Main agent loop - ReAct pattern
        """
        self.conversation_history.append({"role": "user", "content": user_input})
        self.step_count = 0
        
        final_answer = ""
        
        while self.step_count < self.config.max_steps:
            self.step_count += 1
            
            if verbose:
                print(f"\n🤖 AURA Step {self.step_count}/{self.config.max_steps} thinking...")
            
            messages = self._format_history_for_llm()
            tools_openai = self.registry.get_openai_tools()
            
            # Get LLM response
            try:
                if stream_callback:
                    # Streaming mode
                    full_response = ""
                    for chunk in self.llm.chat_stream(messages, tools_openai):
                        full_response += chunk
                        if stream_callback:
                            stream_callback(chunk)
                    llm_response = full_response
                else:
                    llm_response = self.llm.chat(messages, tools_openai, stream=False)
            except Exception as e:
                error_msg = f"LLM Error: {e}"
                if verbose:
                    print(f"❌ {error_msg}")
                self.conversation_history.append({"role": "assistant", "content": error_msg})
                return error_msg
            
            if verbose and not stream_callback:
                print(f"💭 AURA: {llm_response[:500]}...")
            
            # Try to parse as tool call
            tool_call = self._parse_tool_call(llm_response)
            
            if tool_call:
                tool_name = tool_call["tool"]
                arguments = tool_call.get("arguments", {})
                
                if verbose:
                    print(f"🔧 Using tool: {tool_name} with {arguments}")
                
                # Execute tool
                tool_result = self.registry.execute(tool_name, arguments)
                
                if verbose:
                    print(f"📋 Tool result: {tool_result[:500]}...")
                
                # Add to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": llm_response  # The tool call JSON
                })
                self.conversation_history.append({
                    "role": "user",
                    "content": f"TOOL RESULT [{tool_name}]:\n{tool_result}\n\nIf the task is complete, provide final answer. Otherwise continue with next tool."
                })
                
                # If tool was memory related or final, check if we should continue
                # Continue loop
            else:
                # No tool call - this is final answer
                final_answer = llm_response
                self.conversation_history.append({"role": "assistant", "content": final_answer})
                if verbose:
                    print(f"\n✅ AURA Final Answer in {self.step_count} steps")
                break
        else:
            # Max steps reached
            final_answer = f"Reached max steps ({self.config.max_steps}). Last response: {llm_response}\n\nI've been working for {self.config.max_steps} steps - let me summarize what I found."
            self.conversation_history.append({"role": "assistant", "content": final_answer})
        
        return final_answer
    
    def chat_simple(self, message: str) -> str:
        """Simple chat without tools (for quick responses)"""
        messages = self._format_history_for_llm()
        messages.append({"role": "user", "content": message})
        return self.llm.chat(messages, stream=False)
    
    def clear_history(self):
        self.conversation_history = []
        self.step_count = 0
    
    def get_tools_list(self) -> str:
        return self.registry.get_prompt_description()
