"""Settings come from the argument, then the environment, and a missing one says what to set."""

import pytest

from doc2pages.config import ENV_PREFIX, PLACEHOLDER_API_KEY, resolve
from doc2pages.errors import ConfigError


def test_base_url_and_model_have_no_default():
    with pytest.raises(ConfigError) as e:
        resolve()
    assert "DOC2PAGES_BASE_URL" in str(e.value) and "DOC2PAGES_MODEL" in str(e.value)


def test_the_environment_fills_in_what_the_call_leaves_out(monkeypatch):
    monkeypatch.setenv(f"{ENV_PREFIX}BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv(f"{ENV_PREFIX}MODEL", "your-model")
    s = resolve()
    assert s.base_url == "http://localhost:11434/v1" and s.model == "your-model"
    assert s.api_key == PLACEHOLDER_API_KEY


def test_the_argument_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv(f"{ENV_PREFIX}MODEL", "from-env")
    s = resolve(base_url="http://localhost:11434/v1", model="from-argument")
    assert s.model == "from-argument"


def test_openai_api_key_is_the_last_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = resolve(base_url="http://localhost:11434/v1", model="m")
    assert s.api_key == "sk-test"


def test_the_image_settings_fall_back_to_the_chat_settings():
    s = resolve(base_url="http://localhost:11434/v1", model="m", api_key="k")
    assert s.image_base_url == s.base_url and s.image_model == s.model and s.image_api_key == "k"
    own = resolve(base_url="http://a/v1", model="m", image_base_url="http://b/v1",
                  image_model="draw", image_api_key="k2")
    assert own.image_base_url == "http://b/v1" and own.image_model == "draw"
    assert own.image_api_key == "k2"


def test_a_language_outside_the_two_is_refused():
    with pytest.raises(ConfigError) as e:
        resolve(base_url="http://a/v1", model="m", language="fr")
    assert "de, en" in str(e.value)


def test_a_switch_reads_true_and_false_from_the_environment(monkeypatch):
    monkeypatch.setenv(f"{ENV_PREFIX}IMAGES", "yes")
    assert resolve(base_url="http://a/v1", model="m").images is True
    monkeypatch.setenv(f"{ENV_PREFIX}IMAGES", "off")
    assert resolve(base_url="http://a/v1", model="m").images is False
    monkeypatch.setenv(f"{ENV_PREFIX}IMAGES", "maybe")
    with pytest.raises(ConfigError):
        resolve(base_url="http://a/v1", model="m")


def test_a_window_too_small_is_refused_up_front():
    with pytest.raises(ConfigError) as e:
        resolve(base_url="http://a/v1", model="m", context_tokens=4096)
    assert "context" in str(e.value)


def test_a_limit_must_be_greater_than_zero():
    with pytest.raises(ConfigError):
        resolve(base_url="http://a/v1", model="m", max_files=0)
