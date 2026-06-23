from __future__ import annotations

import argparse

from rechner_pipeline.cli import _add_common_options, _options_from_namespace


def test_openai_default_model_is_openai_model() -> None:
    ap = argparse.ArgumentParser()
    _add_common_options(ap)

    ns = ap.parse_args([])
    options = _options_from_namespace(ns)

    assert options.provider == "openai"
    assert options.model == "gpt-5.2"
