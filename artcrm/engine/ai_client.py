"""
AI Client - Unified interface for all AI backends.
Supports: Claude API, DeepSeek Chat, DeepSeek Reasoner.
"""

import logging
from typing import Optional

import requests
from anthropic import Anthropic

from artcrm.config import config

logger = logging.getLogger(__name__)

MODEL_CHOICES = ['claude', 'deepseek-chat', 'deepseek-reasoner']


# =============================================================================
# CLAUDE CLIENT
# =============================================================================

def call_claude(prompt: str, system: Optional[str] = None, max_tokens: int = 2000) -> str:
    """Call Claude API. Returns generated text."""
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    try:
        logger.debug("Calling Claude API")
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            system=system if system else "You are a professional writer helping an artist with gallery outreach.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise RuntimeError(f"Failed to call Claude API: {e}")


# =============================================================================
# DEEPSEEK CLIENT
# =============================================================================

def call_deepseek(
    prompt: str,
    model: str = 'deepseek-chat',
    system: Optional[str] = None,
    max_tokens: int = 2000
) -> str:
    """Call DeepSeek API (OpenAI-compatible). Returns generated text."""
    if not config.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set in environment")

    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        logger.debug(f"Calling DeepSeek API with model {model}")
        response = requests.post(url, json=payload, headers=headers, timeout=(10, 120), verify=True)
        response.raise_for_status()

        result = response.json()
        return result['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        logger.error(f"DeepSeek API error: {e}")
        raise RuntimeError(f"Failed to call DeepSeek API: {e}")
    except (KeyError, IndexError) as e:
        logger.error(f"DeepSeek response parse error: {e}")
        raise RuntimeError(f"Unexpected DeepSeek response format: {e}")


# =============================================================================
# UNIFIED ROUTER
# =============================================================================

def call_ai(
    prompt: str,
    model: str,
    system: Optional[str] = None,
    max_tokens: int = 2000
) -> str:
    """
    Route an AI call to the appropriate backend.

    Args:
        prompt: User prompt text
        model: One of 'claude', 'deepseek-chat', 'deepseek-reasoner'
        system: Optional system prompt
        max_tokens: Max tokens to generate

    Returns: Generated text
    """
    if model == 'claude':
        return call_claude(prompt, system=system, max_tokens=max_tokens)
    elif model in ('deepseek-chat', 'deepseek-reasoner'):
        return call_deepseek(prompt, model=model, system=system, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unknown AI model '{model}'. Choose from: {', '.join(MODEL_CHOICES)}")
