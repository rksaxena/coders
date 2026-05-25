import json
from typing import AsyncIterator, List, NoReturn, Optional, Union

import aiohttp

from src.swarm_coder.config.config import config
from src.swarm_coder.core.logger import logger


def _print_metrics(data_dict: dict) -> None:
    if data_dict.get("done"):
        prompt_eval_count = data_dict.get("prompt_eval_count", 0)
        eval_count = data_dict.get("eval_count", 0)
        eval_duration_ns = data_dict.get("eval_duration", 0)
        if eval_duration_ns > 0:
            tokens_per_sec = eval_count / (eval_duration_ns / 1e9)
            logger.info(
                f"[Ollama Usage] Prompt Tokens: {prompt_eval_count} | "
                f"Output Tokens: {eval_count} | Speed: {tokens_per_sec:.2f} t/s"
            )


def _handle_error(e: Optional[Exception]) -> NoReturn:
    if e is None:
        raise ValueError("No valid models provided or unknown error occurred.")
    if isinstance(e, aiohttp.ClientError):
        raise RuntimeError(f"Ollama API request failed: {e}") from e
    if isinstance(e, RuntimeError):
        raise e
    raise ValueError(f"Failed to parse Ollama response: {e}") from e


class OllamaClient:
    """
    Client for interacting with a local Ollama instance.
    """

    def __init__(self, base_url: str = "http://localhost:11434/api/generate"):
        self.base_url = base_url

    async def generate(
        self,
        model: Union[str, List[str]],
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Union[str, AsyncIterator[str]]:
        """
        Sends a generation request to Ollama.

        Args:
            model (Union[str, List[str]]): The model name or a prioritized list of models
                                        to try as fallbacks.
            prompt (str): The user prompt.
            system (Optional[str]): Optional system prompt.
            stream (bool): Whether to stream the response.

        Returns:
            Union[str, AsyncIterator[str]]: The generated response text,
            or an iterator of response chunks.

        Raises:
            RuntimeError: If the HTTP request fails.
            ValueError: If the response cannot be parsed.
        """
        models = [model] if isinstance(model, str) else model

        # Explicitly force the network socket to close upon delivery
        headers = {"Connection": "close"}

        timeout = aiohttp.ClientTimeout(
            total=config.api_timeout.get("total"),
            sock_read=config.api_timeout.get("sock_read", 120),
            connect=config.api_timeout.get("connect", 15),
        )

        if stream:
            return self._stream_generator(models, prompt, system, headers, timeout)

        return await self._sync_generator(models, prompt, system, headers, timeout)

    async def _stream_generator(
        self,
        models: List[str],
        prompt: str,
        system: Optional[str],
        headers: dict,
        timeout: aiohttp.ClientTimeout,
    ) -> AsyncIterator[str]:
        last_error = None
        for current_model in models:
            payload = {
                "model": current_model,
                "prompt": prompt,
                "stream": True,
                "options": {"num_ctx": config.ollama_num_ctx},
            }
            if system:
                payload["system"] = system

            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.base_url, json=payload, headers=headers
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            if response.status == 404:
                                raise RuntimeError(
                                    f"Ollama returned 404 Not Found for '{current_model}'.\n"
                                    f"Ensure the exact model name exists in `ollama list` "
                                    f"and your server is running. Details: {error_text}"
                                )
                            raise RuntimeError(
                                f"Ollama API error {response.status}: {error_text}"
                            )

                        async for line in response.content:
                            if line:
                                chunk = json.loads(line.decode("utf-8"))
                                _print_metrics(chunk)
                                if "response" in chunk:
                                    yield chunk["response"]
                                elif (
                                    "message" in chunk and "content" in chunk["message"]
                                ):
                                    yield chunk["message"]["content"]
                                if chunk.get("done"):
                                    break
                        return  # Success, exit the fallback loop
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Model '{current_model}' failed during streaming: {e}. "
                    f"Trying next model..."
                )
                continue

        _handle_error(last_error)

    async def _sync_generator(
        self,
        models: List[str],
        prompt: str,
        system: Optional[str],
        headers: dict,
        timeout: aiohttp.ClientTimeout,
    ) -> str:
        last_error = None
        for current_model in models:
            payload = {
                "model": current_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": config.ollama_num_ctx},
            }
            if system:
                payload["system"] = system

            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        self.base_url, json=payload, headers=headers
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            if response.status == 404:
                                raise RuntimeError(
                                    f"Ollama returned 404 Not Found for '{current_model}'.\n"
                                    f"Ensure the exact model name exists in `ollama list` "
                                    f"and your server is running. Details: {error_text}"
                                )
                            raise RuntimeError(
                                f"Ollama API error {response.status}: {error_text}"
                            )

                        data = await response.json()
                        _print_metrics(data)

                        if "response" in data:
                            return data["response"]
                        if "message" in data and "content" in data["message"]:
                            return data["message"]["content"]
                        return str(data)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Model '{current_model}' failed: {e}. Trying next model..."
                )
                continue

        _handle_error(last_error)
