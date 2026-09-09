"""Unit tests for FallbackAdapter (adapters/fallback.py)."""

from unittest.mock import patch

import pytest

from arc_agi_benchmarking.adapters.fallback import FallbackAdapter
from arc_agi_benchmarking.adapters.provider import ProviderAdapter
from arc_agi_benchmarking.schemas import ModelConfig, ModelPricing

CALL_LOG = []


def _reset_log():
    CALL_LOG.clear()


class FakeSuccessAdapter(ProviderAdapter):
    """Fake adapter registered under provider 'fakesuccess'; always succeeds."""

    def init_client(self):
        return None

    def make_prediction(self, prompt, task_id=None, test_id=None, pair_index=None):
        CALL_LOG.append(self.config)
        return f"answer-from-{self.config}"

    def extract_json_from_response(self, input_response):
        return [[0]]


class FakeFailAdapter(ProviderAdapter):
    """Fake adapter registered under provider 'fakefail'; always raises."""

    def init_client(self):
        return None

    def make_prediction(self, prompt, task_id=None, test_id=None, pair_index=None):
        CALL_LOG.append(self.config)
        raise RuntimeError(f"{self.config} deliberately failed")

    def extract_json_from_response(self, input_response):
        return [[0]]


def _config(name, provider, **extra):
    return ModelConfig(
        name=name,
        model_name=name,
        provider=provider,
        api_key_env="UNUSED_TEST_API_KEY",
        pricing=ModelPricing(date="2026-01-01", input=0.0, output=0.0),
        **extra,
    )


CONFIGS = {
    "ok-a": _config("ok-a", "fakesuccess"),
    "ok-b": _config("ok-b", "fakesuccess"),
    "bad-a": _config("bad-a", "fakefail"),
    "bad-b": _config("bad-b", "fakefail"),
    "nonexistent-config-with-bad-provider": _config(
        "nonexistent-config-with-bad-provider", "totally-unregistered-provider"
    ),
}


def _fake_read_models_config(name):
    return CONFIGS[name]


@pytest.fixture(autouse=True)
def patched_registry():
    _reset_log()
    with (
        patch(
            "arc_agi_benchmarking.adapters.fallback._ADAPTER_BY_PROVIDER",
            {"fakesuccess": FakeSuccessAdapter, "fakefail": FakeFailAdapter},
        ),
        patch(
            "arc_agi_benchmarking.adapters.fallback.read_models_config",
            side_effect=_fake_read_models_config,
        ),
        # ProviderAdapter.__init__ (the base class every adapter -- including
        # each fake sub-adapter -- goes through) calls read_models_config via
        # its OWN import binding in provider.py, not fallback.py's. Both must
        # be patched.
        patch(
            "arc_agi_benchmarking.adapters.provider.read_models_config",
            side_effect=_fake_read_models_config,
        ),
        patch(
            "arc_agi_benchmarking.adapters.fallback.read_provider_rate_limits",
            return_value={},
        ),
    ):
        yield


def _make_fallback(chain, config_name="fallback-under-test"):
    CONFIGS[config_name] = _config(config_name, "fallback", fallback_chain=chain)
    return FallbackAdapter(config_name)


def test_first_adapter_success_short_circuits():
    adapter = _make_fallback(["ok-a", "ok-b"])
    result = adapter.make_prediction("prompt", task_id="t1", pair_index=0)
    assert result == "answer-from-ok-a"
    assert CALL_LOG == ["ok-a"]  # ok-b never invoked


def test_falls_back_to_next_on_failure():
    adapter = _make_fallback(["bad-a", "ok-b"])
    result = adapter.make_prediction("prompt", task_id="t1", pair_index=0)
    assert result == "answer-from-ok-b"
    assert CALL_LOG == ["bad-a", "ok-b"]


def test_all_fail_raises_last_error():
    adapter = _make_fallback(["bad-a", "bad-b"])
    with pytest.raises(RuntimeError, match="bad-b deliberately failed"):
        adapter.make_prediction("prompt", task_id="t1", pair_index=0)
    assert CALL_LOG == ["bad-a", "bad-b"]


def test_missing_fallback_chain_raises_value_error():
    CONFIGS["no-chain"] = _config("no-chain", "fallback")
    with pytest.raises(ValueError, match="fallback_chain"):
        FallbackAdapter("no-chain")


def test_unsupported_provider_in_chain_raises_value_error():
    with pytest.raises(ValueError, match="unsupported provider"):
        _make_fallback(["ok-a", "nonexistent-config-with-bad-provider"])
