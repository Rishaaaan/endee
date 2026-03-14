import os
import logging
import requests


logger = logging.getLogger(__name__)


class GroqLLMClient:
    def __init__(self, api_key=None, base_url=None, model=None, timeout_seconds=45):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.base_url = base_url or os.environ.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        self.model = model or os.environ.get("GROQ_MODEL") or "meta-llama/llama-4-scout-17b-16e-instruct"
        self.timeout_seconds = timeout_seconds

    def is_configured(self):
        return bool(self.api_key)

    def chat_completion(self, messages, temperature=0.2, max_tokens=700):
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Configure it as an environment variable.")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        if resp.status_code >= 400:
            logger.error("Groq API error %s: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Groq API request failed: HTTP {resp.status_code}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Groq API returned no choices")

        message = choices[0].get("message") or {}
        return (message.get("content") or "").strip()
