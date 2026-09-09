"""A meta-adapter that tries an ordered chain of real provider adapters.

Motivation: a single free/cheap provider's rate limit or quota can stall an
entire benchmark run. FallbackAdapter lets one model config name (e.g.
"fallback-nemotron-then-allam") wrap several real configs -- each backed by a
different provider -- and tries them in order for every prediction, moving to
the next only when the current one raises. The Attempt returned is whichever
sub-adapter actually answered, so its metadata (model, provider, cost, usage)
reflects the real provider that produced it -- nothing is faked or averaged.

Config shape (models.yml):
    - name: "fallback-nemotron-then-allam"
      model_name: "fallback"
      provider: "fallback"
      fallback_chain:
        - "openrouter-nemotron-3-super"
        - "groq-allam-2-7b"
      pricing:
        date: "2026-09-09"
        input: 0.0   # unused -- real cost comes from whichever chain member
        output: 0.0  # actually answered; see each sub-adapter's own pricing.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from .provider import ProviderAdapter
from .anthropic import AnthropicAdapter
from .open_ai import OpenAIAdapter
from .deepseek import DeepseekAdapter
from .gemini import GeminiAdapter
from .hugging_face_fireworks import HuggingFaceFireworksAdapter
from .fireworks import FireworksAdapter
from .grok import GrokAdapter
from .openrouter import OpenRouterAdapter
from .dashscope import DashScopeAdapter
from .mulerouter import MuleRouterAdapter
from .xai import XAIAdapter
from .claudeagentsdk import ClaudeagentsdkAdapter
from .codexcli import CodexcliAdapter
from .together import TogetherAdapter
from .groq import GroqAdapter
from ..schemas import Attempt
from ..utils.task_utils import read_models_config, read_provider_rate_limits
from ..utils.rate_limiter import RequestRateLimiter

logger = logging.getLogger(__name__)

# Kept in sync with main.py's PROVIDER_ADAPTERS by hand -- duplicated here
# (rather than imported from main.py) to avoid a circular import, since
# main.py itself imports from this package. Adding a new provider means
# updating both dicts.
_ADAPTER_BY_PROVIDER = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "deepseek": DeepseekAdapter,
    "gemini": GeminiAdapter,
    "huggingfacefireworks": HuggingFaceFireworksAdapter,
    "fireworks": FireworksAdapter,
    "grok": GrokAdapter,
    "openrouter": OpenRouterAdapter,
    "dashscope": DashScopeAdapter,
    "mulerouter": MuleRouterAdapter,
    "xai": XAIAdapter,
    "claudeagentsdk": ClaudeagentsdkAdapter,
    "codexcli": CodexcliAdapter,
    "together": TogetherAdapter,
    "groq": GroqAdapter,
}

_DEFAULT_RATE = 25.0
_DEFAULT_PERIOD = 60.0


def _build_rate_limiter(model_config) -> Optional[RequestRateLimiter]:
    """Mirror cli/run_all.py's rate limiter selection, minus its cross-process
    divisor/sharing logic (not needed for calls made inside one adapter)."""
    model_rate_limit = model_config.kwargs.get("rate_limit")
    if model_rate_limit:
        rate = model_rate_limit.get("rate", _DEFAULT_RATE)
        period = model_rate_limit.get("period", _DEFAULT_PERIOD)
    else:
        try:
            provider_limits = read_provider_rate_limits()
        except Exception:
            provider_limits = {}
        limits = provider_limits.get(model_config.provider)
        rate = limits["rate"] if limits else _DEFAULT_RATE
        period = limits["period"] if limits else _DEFAULT_PERIOD

    if period <= 0:
        return None
    rps = rate / period
    return RequestRateLimiter(rate=rps, capacity=max(1.0, rps))


class FallbackAdapter(ProviderAdapter):
    """Tries each config in ``fallback_chain`` in order until one succeeds."""

    def init_client(self) -> List[ProviderAdapter]:
        chain = self.model_config.kwargs.get("fallback_chain")
        if not chain:
            raise ValueError(
                f"Config '{self.config}' uses provider 'fallback' but has no "
                "fallback_chain (a list of other config names) in its kwargs."
            )

        adapters: List[ProviderAdapter] = []
        for sub_config_name in chain:
            sub_config = read_models_config(sub_config_name)
            adapter_cls = _ADAPTER_BY_PROVIDER.get(sub_config.provider)
            if adapter_cls is None:
                raise ValueError(
                    f"fallback_chain entry '{sub_config_name}' has unsupported "
                    f"provider '{sub_config.provider}'"
                )
            adapters.append(
                adapter_cls(
                    sub_config_name,
                    request_limiter=_build_rate_limiter(sub_config),
                    raw_api_logger=self.raw_api_logger,
                )
            )
        logger.info(
            "FallbackAdapter '%s' chain: %s",
            self.config,
            " -> ".join(chain),
        )
        return adapters

    def make_prediction(
        self,
        prompt: str,
        task_id: Optional[str] = None,
        test_id: Optional[str] = None,
        pair_index: int = None,
    ) -> Attempt:
        last_error: Optional[BaseException] = None
        for adapter in self.client:
            provider_name = adapter.model_config.provider
            try:
                return adapter.make_prediction(
                    prompt, task_id=task_id, test_id=test_id, pair_index=pair_index
                )
            except Exception as error:  # noqa: BLE001 - deliberately broad: any
                # failure (rate limit, quota, context-length, auth, transport)
                # should fall through to the next provider in the chain.
                last_error = error
                logger.warning(
                    "FallbackAdapter '%s': provider '%s' (%s) failed for "
                    "task_id=%s, pair_index=%s: %s. Trying next in chain.",
                    self.config,
                    provider_name,
                    adapter.config,
                    task_id,
                    pair_index,
                    error,
                )
        assert last_error is not None  # chain is non-empty, checked in init_client
        raise last_error

    def extract_json_from_response(self, input_response: str) -> List[List[int]]:
        # Never actually invoked: each sub-adapter parses its own response
        # inside its own make_prediction(). Delegated for interface
        # completeness only.
        return self.client[0].extract_json_from_response(input_response)
