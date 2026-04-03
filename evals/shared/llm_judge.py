"""LLM judge wrapper for OpenAI-compatible APIs.

Provides structured JSON responses from any OpenAI-compatible endpoint
(OpenAI, Ollama, vLLM, etc.) via environment-variable configuration.
"""

import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# Maximum number of additional attempts after the first on JSON parse failure.
_MAX_RETRIES = 2


class LLMJudge:
    """Thin wrapper around an OpenAI-compatible chat-completion endpoint.

    All configuration is read from environment variables at construction time
    so that callers never embed credentials or URLs in source code:

        EVAL_LLM_BASE_URL  — e.g. "https://api.openai.com/v1" or a local Ollama URL
        EVAL_LLM_API_KEY   — API key (use a dummy value for keyless local endpoints)
        EVAL_LLM_MODEL     — model name to pass in every request
    """

    def __init__(self) -> None:
        base_url = os.environ.get("EVAL_LLM_BASE_URL")
        api_key = os.environ.get("EVAL_LLM_API_KEY")
        model = os.environ.get("EVAL_LLM_MODEL")

        missing = [
            name
            for name, val in [
                ("EVAL_LLM_BASE_URL", base_url),
                ("EVAL_LLM_API_KEY", api_key),
                ("EVAL_LLM_MODEL", model),
            ]
            if not val
        ]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Store model separately; client only needs connection details.
        self._model: str = model  # type: ignore[assignment]  # validated above
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def judge(self, prompt: str, response_schema: dict) -> dict:
        """Send *prompt* to the LLM and parse a structured JSON response.

        The schema is communicated to the model as a natural-language instruction
        appended to the prompt, describing the exact JSON keys expected. The model
        is instructed to respond with *only* valid JSON.

        Args:
            prompt: The evaluation prompt.  Should describe the task clearly.
            response_schema: A dict whose keys name the expected top-level fields
                and whose values are human-readable descriptions of each field.
                Example: {"score": "integer 1-5", "reasoning": "brief explanation"}

        Returns:
            Parsed dict matching (a superset of) response_schema keys.

        Raises:
            ValueError: If a valid JSON object cannot be obtained after all retries.
        """
        schema_instruction = _build_schema_instruction(response_schema)
        full_prompt = f"{prompt.rstrip()}\n\n{schema_instruction}"
        return self._call_with_retry(full_prompt)

    def judge_with_rubric(self, prompt: str, rubric: dict[str, list[str]]) -> dict:
        """Score a response against a multi-dimension rubric.

        Each rubric dimension maps to a list of allowed string values (ordered
        from worst to best by convention).  The LLM must return exactly one of
        the listed values for each dimension.

        Args:
            prompt: The evaluation prompt describing what should be scored.
            rubric: Mapping of dimension names to their valid value options.
                Example: {"clarity": ["poor", "fair", "good", "excellent"]}

        Returns:
            Dict mapping each dimension name to the LLM-selected value.
            An additional ``"reasoning"`` key is always present with a brief
            explanation for all dimension choices.

        Raises:
            ValueError: If the LLM response cannot be parsed or contains invalid
                values for any rubric dimension.
        """
        rubric_instruction = _build_rubric_instruction(rubric)
        full_prompt = f"{prompt.rstrip()}\n\n{rubric_instruction}"
        raw = self._call_with_retry(full_prompt)

        # Validate that all dimensions are present and have permitted values,
        # and that the mandatory "reasoning" key is included.
        errors: list[str] = []
        for dimension, options in rubric.items():
            if dimension not in raw:
                errors.append(f"Missing dimension '{dimension}' in LLM response")
            elif raw[dimension] not in options:
                errors.append(
                    f"Dimension '{dimension}' returned '{raw[dimension]}'; "
                    f"expected one of {options}"
                )
        if "reasoning" not in raw:
            errors.append("Missing required key 'reasoning' in LLM response")
        if errors:
            raise ValueError(
                "LLM rubric response failed validation:\n" + "\n".join(errors)
            )

        return raw

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_with_retry(self, prompt: str) -> dict:
        """Call the LLM and retry up to _MAX_RETRIES times on JSON parse failure."""
        last_exc: Exception | None = None

        for attempt in range(1 + _MAX_RETRIES):
            logger.debug(
                "LLMJudge call attempt %d/%d | model=%s | prompt=%r",
                attempt + 1,
                1 + _MAX_RETRIES,
                self._model,
                prompt,
            )

            response_text = self._complete(prompt)
            logger.debug("LLMJudge raw response: %r", response_text)

            try:
                result = _parse_json(response_text)
                return result
            except ValueError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "JSON parse failed on attempt %d (retrying): %s",
                        attempt + 1,
                        exc,
                    )
                else:
                    logger.error(
                        "JSON parse failed on final attempt %d: %s",
                        attempt + 1,
                        exc,
                    )

        raise ValueError(
            f"Could not parse valid JSON from LLM after {1 + _MAX_RETRIES} attempts. "
            f"Last error: {last_exc}"
        )

    def _complete(self, prompt: str) -> str:
        """Send a single chat-completion request and return the assistant text."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


# ------------------------------------------------------------------
# Module-level helpers (not part of public API)
# ------------------------------------------------------------------

def _build_schema_instruction(schema: dict[str, Any]) -> str:
    """Build a prompt suffix that instructs the model to return JSON."""
    field_lines = "\n".join(
        f'  "{key}": {desc}' for key, desc in schema.items()
    )
    return (
        "Respond with ONLY a valid JSON object — no markdown fences, "
        "no extra commentary.\n"
        "Required fields:\n"
        f"{field_lines}"
    )


def _build_rubric_instruction(rubric: dict[str, list[str]]) -> str:
    """Build a prompt suffix for rubric-based scoring."""
    dimension_lines = "\n".join(
        f'  "{dim}": one of {opts}' for dim, opts in rubric.items()
    )
    return (
        "Respond with ONLY a valid JSON object — no markdown fences, "
        "no extra commentary.\n"
        "Required fields (use EXACTLY one of the listed options per dimension):\n"
        f"{dimension_lines}\n"
        '  "reasoning": brief explanation covering all dimensions'
    )


def _parse_json(text: str) -> dict:
    """Extract and parse the first JSON object from *text*.

    Strips optional markdown code fences before attempting to parse.
    """
    # Strip common markdown fences the model may add despite instructions.
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove opening fence (```json or ```) and closing fence (```)
        inner_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner_lines.append(line)
        stripped = "\n".join(inner_lines).strip()

    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc} | raw text: {text!r}") from exc

    if not isinstance(result, dict):
        raise ValueError(
            f"Expected a JSON object (dict), got {type(result).__name__}: {text!r}"
        )
    return result
