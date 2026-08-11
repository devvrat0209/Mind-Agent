from typing import List, Dict, Any, Generator, Optional
import os
from .config import AgentConfig

class LLMClient:
    """Multi-provider LLM Client with OpenAI-compatible interface"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.provider = config.llm_provider.lower()
        self.model = config.llm_model
        self._client = None
        self._init_client()
    
    def _init_client(self):
        llm_cfg = self.config.get_llm_config()
        provider = self.provider
        
        if provider in ("openai", "openrouter", "groq", "together", "ollama", "custom"):
            try:
                from openai import OpenAI
                kwargs = {}
                if llm_cfg.get("api_key"):
                    kwargs["api_key"] = llm_cfg["api_key"]
                if llm_cfg.get("base_url"):
                    kwargs["base_url"] = llm_cfg["base_url"]
                self._client = OpenAI(**kwargs)
                self._mode = "openai"
            except ImportError:
                raise ImportError("openai package required. pip install openai")
        elif provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=llm_cfg.get("api_key"))
                self._mode = "anthropic"
            except ImportError:
                raise ImportError("anthropic package required. pip install anthropic")
        elif provider in ("google", "gemini"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=llm_cfg.get("api_key"))
                self._client = genai.GenerativeModel(llm_cfg.get("model", "gemini-1.5-flash"))
                self._mode = "google"
            except ImportError:
                raise ImportError("google-generativeai required. pip install google-generativeai")
        else:
            # Default to openai compatible
            from openai import OpenAI
            self._client = OpenAI(
                api_key=llm_cfg.get("api_key") or "sk-dummy",
                base_url=llm_cfg.get("base_url") or "https://api.openai.com/v1"
            )
            self._mode = "openai"
    
    def chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None, stream: bool = False) -> str:
        """Non-streaming chat completion"""
        if self._mode == "openai":
            return self._chat_openai(messages, tools, stream=False)
        elif self._mode == "anthropic":
            return self._chat_anthropic(messages, tools)
        elif self._mode == "google":
            return self._chat_google(messages)
        else:
            return self._chat_openai(messages, tools, stream=False)
    
    def chat_stream(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Streaming chat"""
        if self._mode == "openai":
            yield from self._chat_openai_stream(messages, tools)
        else:
            # Fallback to non-stream for other providers
            full = self.chat(messages, tools, stream=False)
            # Simulate streaming by words
            for word in full.split():
                yield word + " "
    
    def _chat_openai(self, messages: List[Dict], tools: Optional[List[Dict]] = None, stream: bool = False) -> str:
        kwargs = {
            "model": self.config.get_llm_config().get("model", self.model),
            "messages": messages,
            "temperature": 0.7,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        
        # If tool calls present, return as JSON string for agent to parse
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            tool_call = msg.tool_calls[0]
            return f'{{"tool": "{tool_call.function.name}", "arguments": {tool_call.function.arguments}}}'
        
        return msg.content or ""
    
    def _chat_openai_stream(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        kwargs = {
            "model": self.config.get_llm_config().get("model", self.model),
            "messages": messages,
            "temperature": 0.7,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
        
        response = self._client.chat.completions.create(**kwargs)
        collected_tool = {"name": "", "arguments": ""}
        is_tool = False
        
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                is_tool = True
                tc = delta.tool_calls[0]
                if tc.function.name:
                    collected_tool["name"] = tc.function.name
                if tc.function.arguments:
                    collected_tool["arguments"] += tc.function.arguments
            elif delta.content:
                if not is_tool:
                    yield delta.content
        
        if is_tool and collected_tool["name"]:
            # Yield the complete tool call as final chunk
            yield f'\n{{"tool": "{collected_tool["name"]}", "arguments": {collected_tool["arguments"]}}}'
    
    def _chat_anthropic(self, messages: List[Dict], tools=None) -> str:
        # Convert messages
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                conv_messages.append(m)
        
        kwargs = {
            "model": self.config.get_llm_config().get("model", "claude-3-haiku-20240307"),
            "max_tokens": 4096,
            "messages": conv_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        # Tools conversion would go here
        response = self._client.messages.create(**kwargs)
        return response.content[0].text
    
    def _chat_google(self, messages: List[Dict]) -> str:
        # Convert to Gemini format
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        response = self._client.generate_content(prompt)
        return response.text

# Mock client for testing without API key
class MockLLMClient:
    def __init__(self, config: AgentConfig):
        self.config = config
    
    def chat(self, messages, tools=None, stream=False):
        last_user = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user = m["content"]
                break
        return f"[MOCK MODE - No API key set] You said: {last_user}\n\nI am AURA, your AI agent. To enable full capabilities, set OPENAI_API_KEY in .env\n\nAvailable tools: {[t['function']['name'] for t in (tools or [])][:5]}"
    
    def chat_stream(self, messages, tools=None):
        text = self.chat(messages, tools)
        for word in text.split():
            yield word + " "
