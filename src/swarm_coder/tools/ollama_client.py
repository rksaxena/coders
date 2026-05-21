import aiohttp
import json
from typing import Dict, Any, Optional, Union, AsyncIterator
from rich import print

class OllamaClient:
    """
    Client for interacting with a local Ollama instance.
    """
    def __init__(self, base_url: str = "http://localhost:11434/api/generate"):
        self.base_url = base_url

    async def generate(self, model: str, prompt: str, system: Optional[str] = None, stream: bool = False) -> Union[str, AsyncIterator[str]]:
        """
        Sends a generation request to Ollama.
        
        Args:
            model (str): The model name (e.g., 'qwen2.5-coder').
            prompt (str): The user prompt.
            system (Optional[str]): Optional system prompt.
            stream (bool): Whether to stream the response.
            
        Returns:
            Union[str, AsyncIterator[str]]: The generated response text, or an iterator of response chunks.
            
        Raises:
            RuntimeError: If the HTTP request fails.
            ValueError: If the response cannot be parsed.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "num_ctx": 16384
            }
        }
        if system:
            payload["system"] = system
        # Explicitly force the network socket to close upon delivery
        headers = {
            "Connection": "close"
        }

        def print_metrics(data_dict: dict):
            if data_dict.get("done"):
                prompt_eval_count = data_dict.get("prompt_eval_count", 0)
                eval_count = data_dict.get("eval_count", 0)
                eval_duration_ns = data_dict.get("eval_duration", 0)
                if eval_duration_ns > 0:
                    tokens_per_sec = eval_count / (eval_duration_ns / 1e9)
                    print(f"[bold cyan][Ollama Usage][/bold cyan] Prompt Tokens: {prompt_eval_count} | Output Tokens: {eval_count} | Speed: {tokens_per_sec:.2f} t/s")

        timeout = aiohttp.ClientTimeout(total=None, sock_read=120, connect=15)

        try:
            if stream:
                async def stream_generator() -> AsyncIterator[str]:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(self.base_url, json=payload, headers=headers) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                if response.status == 404:
                                    raise RuntimeError(f"Ollama returned 404 Not Found.\n"
                                                       f"Ensure the exact model name exists in `ollama list` and your server is running. Details: {error_text}")
                                else:
                                    raise RuntimeError(f"Ollama API error {response.status}: {error_text}")
                            async for line in response.content:
                                if line:
                                    chunk = json.loads(line.decode('utf-8'))
                                    print_metrics(chunk)
                                    if "response" in chunk:
                                        yield chunk["response"]
                                    elif "message" in chunk and "content" in chunk["message"]:
                                        yield chunk["message"]["content"]
                                    if chunk.get("done"):
                                        break
                return stream_generator()
            else:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.base_url, json=payload, headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            if response.status == 404:
                                raise RuntimeError(f"Ollama returned 404 Not Found.\n"
                                                   f"Ensure the exact model name exists in `ollama list` and your server is running. Details: {error_text}")
                            else:
                                raise RuntimeError(f"Ollama API error {response.status}: {error_text}")
                        data = await response.json()
                        print_metrics(data)
                        if "response" in data:
                            return data["response"]
                        elif "message" in data and "content" in data["message"]:
                            return data["message"]["content"]
                        else:
                            return str(data)
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Ollama API request failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse Ollama response: {str(e)}")
