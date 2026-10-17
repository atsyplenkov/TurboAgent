"""Backend parameter plumbing: yaml model fields must reach litellm.

Run: python tests/test_backend_params.py   (or: pytest tests/)
No network — litellm and the completion helper are stubbed.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turbo_agent.proxy import backend as backend_mod  # noqa: E402
from turbo_agent.utils import Config  # noqa: E402
from turbo_agent.utils import llm as llm_mod  # noqa: E402


def _config_from_yaml(yaml_text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "turbo-agent.yaml"
        path.write_text(yaml_text)
        return Config(str(path))


def _capture_params(completion, **call_kwargs):
    """Run ``completion`` with litellm stubbed and return the params it built."""
    captured = {}

    class FakeResponse:
        def model_dump(self):
            return {}

    async def fake_acompletion(**params):
        captured.update(params)
        return FakeResponse()

    real = llm_mod.litellm.acompletion
    llm_mod.litellm.acompletion = fake_acompletion
    try:
        asyncio.run(completion(
            "openai/some-model", [{"role": "user", "content": "hi"}],
            **call_kwargs))
    finally:
        llm_mod.litellm.acompletion = real
    return captured


def test_base_url_reaches_litellm():
    captured = _capture_params(llm_mod.llm_completion, api_key="test-key",
                               base_url="http://localhost:9002/v1")
    assert captured["base_url"] == "http://localhost:9002/v1"
    assert captured["api_key"] == "test-key"


def test_base_url_reaches_litellm_when_streaming():
    captured = _capture_params(llm_mod.llm_stream_completion,
                               api_key="test-key",
                               base_url="http://localhost:9002/v1")
    assert captured["base_url"] == "http://localhost:9002/v1"
    assert captured["stream"] is True


def test_base_url_is_omitted_when_not_configured():
    captured = _capture_params(llm_mod.llm_completion, api_key="test-key")
    assert "base_url" not in captured


def test_backend_entries_carry_base_url():
    """The per-candidate entry dicts built by _model_entries() must include
    base_url, or it never reaches llm_completion()'s kwargs at all."""
    cfg = _config_from_yaml("""
backend:
  models:
    - name: openai/some-model
      base_url: http://localhost:9002/v1
      api_key: test-key
      num_candidates: 2
""")
    captured = []

    async def fake_completion(**kwargs):
        captured.append(kwargs)
        return {"choices": [{"message": {"content": "x"}}]}

    real = backend_mod.llm_completion
    backend_mod.llm_completion = fake_completion
    try:
        backend = backend_mod.Backend(cfg)
        responses = asyncio.run(backend._gather_completions({"messages": []}))
    finally:
        backend_mod.llm_completion = real

    assert len(responses) == 2
    assert all(c["base_url"] == "http://localhost:9002/v1" for c in captured)
    assert all(c["model"] == "openai/some-model" for c in captured)


def test_backend_base_url_is_resolved_from_the_environment():
    os.environ["TEST_BACKEND_BASE_URL"] = "http://localhost:9002/v1"
    cfg = _config_from_yaml("""
backend:
  models:
    - name: openai/some-model
      api_key: test-key
      base_url: $TEST_BACKEND_BASE_URL
""")
    assert cfg.models[0]["base_url"] == "http://localhost:9002/v1"
    assert cfg.default_model["base_url"] == "http://localhost:9002/v1"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
