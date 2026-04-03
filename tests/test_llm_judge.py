"""Unit tests for evals.shared.llm_judge.LLMJudge."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from evals.shared.llm_judge import LLMJudge, _parse_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_env(base_url="http://localhost:11434/v1", api_key="test-key", model="gpt-test"):
    """Return a dict of the three required env vars."""
    return {
        "EVAL_LLM_BASE_URL": base_url,
        "EVAL_LLM_API_KEY": api_key,
        "EVAL_LLM_MODEL": model,
    }


def _mock_client_response(text: str) -> MagicMock:
    """Build a mock OpenAI client that returns *text* as the assistant message."""
    choice = MagicMock()
    choice.message.content = text
    completion = MagicMock()
    completion.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ---------------------------------------------------------------------------
# __init__ / env var handling
# ---------------------------------------------------------------------------

class TestLLMJudgeInit:
    def test_raises_when_all_vars_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the three vars if they happen to exist in test environment.
            for k in ("EVAL_LLM_BASE_URL", "EVAL_LLM_API_KEY", "EVAL_LLM_MODEL"):
                os.environ.pop(k, None)
            with pytest.raises(ValueError, match="Missing required environment variables"):
                LLMJudge()

    def test_raises_when_one_var_missing(self):
        env = _make_env()
        del env["EVAL_LLM_MODEL"]
        with patch.dict(os.environ, env, clear=False):
            for k in ("EVAL_LLM_BASE_URL", "EVAL_LLM_API_KEY", "EVAL_LLM_MODEL"):
                if k not in env:
                    os.environ.pop(k, None)
            with pytest.raises(ValueError, match="EVAL_LLM_MODEL"):
                LLMJudge()

    def test_constructs_with_valid_env(self):
        with patch.dict(os.environ, _make_env()):
            with patch("evals.shared.llm_judge.OpenAI") as mock_openai:
                judge = LLMJudge()
                mock_openai.assert_called_once_with(
                    base_url="http://localhost:11434/v1",
                    api_key="test-key",
                )
                assert judge._model == "gpt-test"


# ---------------------------------------------------------------------------
# judge()
# ---------------------------------------------------------------------------

class TestJudge:
    def _make_judge(self) -> LLMJudge:
        with patch.dict(os.environ, _make_env()):
            with patch("evals.shared.llm_judge.OpenAI"):
                return LLMJudge()

    def test_returns_parsed_dict(self):
        judge = self._make_judge()
        response_payload = {"score": 4, "reasoning": "Good work."}
        judge._client = _mock_client_response(json.dumps(response_payload))

        result = judge.judge("Evaluate this.", {"score": "int", "reasoning": "str"})
        assert result == response_payload

    def test_strips_markdown_fences(self):
        judge = self._make_judge()
        fenced = "```json\n{\"score\": 3}\n```"
        judge._client = _mock_client_response(fenced)

        result = judge.judge("prompt", {"score": "int"})
        assert result["score"] == 3

    def test_retries_on_invalid_json_then_succeeds(self):
        judge = self._make_judge()
        bad_response = "not json at all"
        good_response = json.dumps({"score": 5})

        # First two calls return bad JSON; third succeeds.
        choice_bad = MagicMock()
        choice_bad.message.content = bad_response
        choice_good = MagicMock()
        choice_good.message.content = good_response

        completion_bad = MagicMock()
        completion_bad.choices = [choice_bad]
        completion_good = MagicMock()
        completion_good.choices = [choice_good]

        judge._client = MagicMock()
        judge._client.chat.completions.create.side_effect = [
            completion_bad,
            completion_bad,
            completion_good,
        ]

        result = judge.judge("prompt", {"score": "int"})
        assert result["score"] == 5
        assert judge._client.chat.completions.create.call_count == 3

    def test_raises_after_all_retries_exhausted(self):
        judge = self._make_judge()
        judge._client = _mock_client_response("definitely not json")

        with pytest.raises(ValueError, match="Could not parse valid JSON"):
            judge.judge("prompt", {"score": "int"})

    def test_raises_on_non_dict_json(self):
        judge = self._make_judge()
        judge._client = _mock_client_response("[1, 2, 3]")

        with pytest.raises(ValueError, match="Expected a JSON object"):
            judge.judge("prompt", {"score": "int"})


# ---------------------------------------------------------------------------
# judge_with_rubric()
# ---------------------------------------------------------------------------

class TestJudgeWithRubric:
    def _make_judge(self) -> LLMJudge:
        with patch.dict(os.environ, _make_env()):
            with patch("evals.shared.llm_judge.OpenAI"):
                return LLMJudge()

    def test_valid_rubric_response(self):
        judge = self._make_judge()
        rubric = {"clarity": ["poor", "fair", "good"], "depth": ["shallow", "deep"]}
        payload = {"clarity": "good", "depth": "deep", "reasoning": "Solid."}
        judge._client = _mock_client_response(json.dumps(payload))

        result = judge.judge_with_rubric("Assess this.", rubric)
        assert result["clarity"] == "good"
        assert result["depth"] == "deep"

    def test_invalid_dimension_value_raises(self):
        judge = self._make_judge()
        rubric = {"clarity": ["poor", "good"]}
        # LLM returns a value not in the rubric options.
        judge._client = _mock_client_response(
            json.dumps({"clarity": "excellent", "reasoning": "OK"})
        )

        with pytest.raises(ValueError, match="clarity"):
            judge.judge_with_rubric("prompt", rubric)

    def test_missing_dimension_raises(self):
        judge = self._make_judge()
        rubric = {"clarity": ["poor", "good"], "depth": ["shallow", "deep"]}
        # LLM omits "depth".
        judge._client = _mock_client_response(
            json.dumps({"clarity": "good", "reasoning": "Only clarity scored."})
        )

        with pytest.raises(ValueError, match="depth"):
            judge.judge_with_rubric("prompt", rubric)


# ---------------------------------------------------------------------------
# _parse_json helper
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_plain_json(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        assert _parse_json("```json\n{\"a\": 1}\n```") == {"a": 1}

    def test_fenced_without_language_tag(self):
        assert _parse_json("```\n{\"x\": true}\n```") == {"x": True}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="JSON parse error"):
            _parse_json("not valid json")

    def test_array_raises(self):
        with pytest.raises(ValueError, match="Expected a JSON object"):
            _parse_json("[1, 2]")
