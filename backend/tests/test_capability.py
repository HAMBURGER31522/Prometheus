"""Model capability parsing from `pi --offline --list-models` (PLAN 8.7)."""

from prometheus.settings.capability import model_supports_images, parse_capabilities

LIST_OUTPUT = """provider  model                         context  max-out  thinking  images
deepseek  deepseek-flash                1M       384K     yes       yes
deepseek  deepseek-v4-flash             1M       384K     yes       no
zhipu     glm-5.3-flash                 128K     65.5K    yes       no
"""


def test_parse_capabilities():
    caps = parse_capabilities(LIST_OUTPUT)
    assert caps["deepseek-flash"] is True
    assert caps["deepseek-v4-flash"] is False
    assert caps["glm-5.3-flash"] is False


def test_model_supports_images():
    assert model_supports_images(LIST_OUTPUT, "deepseek-flash") is True
    assert model_supports_images(LIST_OUTPUT, "deepseek-v4-flash") is False
    assert model_supports_images(LIST_OUTPUT, "unknown-model") is False


def test_no_models_available_means_no_images():
    assert model_supports_images("No models available", "deepseek-flash") is False
