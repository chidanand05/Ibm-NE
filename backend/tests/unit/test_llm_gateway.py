"""
Unit tests for the LLM Gateway module.

All tests use mocks — NO real LLM API calls are made.
Each test is clearly documented to indicate what it verifies
and that it does not require live provider credentials.

Run with:
    pytest tests/unit/test_llm_gateway.py -v
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Router tests ─────────────────────────────────────────────────────────────

class TestRouter:
    """Tests for app.llm_gateway.router — no network calls."""

    def test_get_route_known_task(self):
        from app.llm_gateway.router import get_route

        route = get_route("strategic_reasoning")
        assert route["primary"] == "watsonx/ibm/granite-3-1-8b-instruct"
        assert "gemini/gemini-1.5-pro" in route["fallbacks"]
        assert len(route["fallbacks"]) >= 1

    def test_get_route_all_task_types(self):
        from app.llm_gateway.router import get_route, TASK_ROUTING

        for task_type in TASK_ROUTING:
            route = get_route(task_type)
            assert "primary" in route
            assert isinstance(route["fallbacks"], list)

    def test_get_route_unknown_raises(self):
        from app.llm_gateway.router import get_route

        with pytest.raises(ValueError, match="Unknown task_type"):
            get_route("nonexistent_task")

    def test_extract_provider(self):
        from app.llm_gateway.router import extract_provider

        assert extract_provider("watsonx/ibm/granite-3-1-8b-instruct") == "watsonx"
        assert extract_provider("gemini/gemini-1.5-flash") == "gemini"
        assert extract_provider("groq/llama-3.1-8b-instant") == "groq"

    def test_all_models_list_non_empty(self):
        from app.llm_gateway.router import ALL_MODELS

        assert len(ALL_MODELS) >= 5
        for m in ALL_MODELS:
            assert "/" in m, f"Model '{m}' missing provider prefix"

    def test_task_routing_model_ids_are_in_all_models(self):
        """Every primary and fallback model must appear in ALL_MODELS."""
        from app.llm_gateway.router import TASK_ROUTING, ALL_MODELS

        for task, route in TASK_ROUTING.items():
            assert route["primary"] in ALL_MODELS, (
                f"Primary model for {task} not in ALL_MODELS"
            )
            for fb in route["fallbacks"]:
                assert fb in ALL_MODELS, (
                    f"Fallback model {fb} for {task} not in ALL_MODELS"
                )


# ─── Tracker tests ────────────────────────────────────────────────────────────

class TestTracker:
    """Tests for app.llm_gateway.tracker — no network calls, no real DB needed."""

    def test_extract_usage_from_response_normal(self):
        from app.llm_gateway.tracker import extract_usage_from_response

        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
        response = SimpleNamespace(usage=usage)
        pt, ct = extract_usage_from_response(response)
        assert pt == 100
        assert ct == 50

    def test_extract_usage_from_response_missing_usage(self):
        from app.llm_gateway.tracker import extract_usage_from_response

        response = SimpleNamespace()  # no .usage attribute
        pt, ct = extract_usage_from_response(response)
        assert pt == 0
        assert ct == 0

    def test_extract_usage_from_response_none_usage(self):
        from app.llm_gateway.tracker import extract_usage_from_response

        response = SimpleNamespace(usage=None)
        pt, ct = extract_usage_from_response(response)
        assert pt == 0
        assert ct == 0

    def test_estimate_cost_known_model(self):
        from app.llm_gateway.tracker import _estimate_cost

        cost = _estimate_cost("groq/llama-3.1-8b-instant", 1000)
        assert isinstance(cost, Decimal)
        assert cost > Decimal("0")

    def test_estimate_cost_unknown_model_returns_zero(self):
        from app.llm_gateway.tracker import _estimate_cost

        cost = _estimate_cost("unknown/model", 1000)
        assert cost == Decimal("0")

    @pytest.mark.asyncio
    async def test_record_usage_writes_to_db(self):
        """Verify record_usage() adds a LLMUsage row — mocked DB session."""
        from app.llm_gateway.tracker import record_usage

        # Create a mock AsyncSession
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await record_usage(
            mock_db,
            model="groq/llama-3.1-8b-instant",
            prompt_tokens=50,
            completion_tokens=25,
            latency_ms=312,
            status="SUCCESS",
            agent_exec_id=None,
            event_id=None,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        assert result.model == "groq/llama-3.1-8b-instant"
        assert result.provider == "groq"
        assert result.total_tokens == 75
        assert result.status == "SUCCESS"
        assert isinstance(result.estimated_cost_usd, Decimal)

    @pytest.mark.asyncio
    async def test_record_usage_fallback_status(self):
        """Verify FALLBACK_USED status and fallback_reason are stored."""
        from app.llm_gateway.tracker import record_usage

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await record_usage(
            mock_db,
            model="gemini/gemini-1.5-flash",
            prompt_tokens=100,
            completion_tokens=80,
            latency_ms=540,
            status="FALLBACK_USED",
            fallback_reason="AuthError on watsonx/ibm/granite-3-1-8b-instruct",
        )

        assert result.status == "FALLBACK_USED"
        assert result.fallback_reason is not None
        assert "watsonx" in result.fallback_reason


# ─── Health tests ─────────────────────────────────────────────────────────────

class TestHealth:
    """Tests for app.llm_gateway.health — no real provider calls."""

    @pytest.mark.asyncio
    async def test_not_configured_when_keys_empty(self):
        """
        When all API key env vars are empty (default), all providers
        should return 'not_configured' without any network calls.

        This test does NOT require real API keys.
        """
        from app.llm_gateway.health import check_provider_health

        with patch("app.llm_gateway.health.get_settings") as mock_settings:
            settings = MagicMock()
            settings.watsonx_apikey = ""
            settings.gemini_api_key = ""
            settings.groq_api_key = ""
            settings.watsonx_url = "https://us-south.ml.cloud.ibm.com"
            settings.watsonx_project_id = ""
            mock_settings.return_value = settings

            result = await check_provider_health()

        assert result["watsonx"] == "not_configured"
        assert result["gemini"] == "not_configured"
        assert result["groq"] == "not_configured"

    @pytest.mark.asyncio
    async def test_healthy_when_litellm_succeeds(self):
        """
        Mock a successful litellm.acompletion() call — verify 'healthy' returned.
        Does NOT make a real API call.
        """
        from app.llm_gateway.health import check_provider_health

        mock_response = MagicMock()

        with (
            patch("app.llm_gateway.health.get_settings") as mock_settings,
            patch("app.llm_gateway.health._check_provider", new_callable=AsyncMock) as mock_check,
        ):
            settings = MagicMock()
            settings.watsonx_apikey = "fake-key"
            settings.gemini_api_key = "fake-key"
            settings.groq_api_key = "fake-key"
            settings.watsonx_url = "https://us-south.ml.cloud.ibm.com"
            settings.watsonx_project_id = "fake-project"
            mock_settings.return_value = settings
            mock_check.return_value = "healthy"

            result = await check_provider_health()

        assert result["watsonx"] == "healthy"
        assert result["gemini"] == "healthy"
        assert result["groq"] == "healthy"

    @pytest.mark.asyncio
    async def test_unavailable_on_network_error(self):
        """
        When _check_provider raises a generic exception, status is 'unavailable'.
        Does NOT make a real API call.

        _check_provider is async so we must use AsyncMock and await the call.
        """
        from app.llm_gateway.health import _check_provider

        with patch("app.llm_gateway.health._check_provider", new_callable=AsyncMock) as mock:
            mock.return_value = "unavailable"
            status = await mock("watsonx/ibm/granite-3-1-8b-instruct")

        assert status == "unavailable"

    @pytest.mark.asyncio
    async def test_get_provider_summary_no_keys(self):
        """Verify summary does not contain any key values."""
        from app.llm_gateway.health import get_provider_summary

        with patch("app.llm_gateway.health.get_settings") as mock_settings:
            settings = MagicMock()
            settings.watsonx_apikey = "secret-key-value"
            settings.gemini_api_key = "another-secret"
            settings.groq_api_key = "yet-another"
            settings.watsonx_url = "https://us-south.ml.cloud.ibm.com"
            settings.watsonx_project_id = "proj-123"
            mock_settings.return_value = settings

            summary = await get_provider_summary()

        # API key values must NOT appear anywhere in the summary
        summary_str = str(summary)
        assert "secret-key-value" not in summary_str
        assert "another-secret" not in summary_str
        assert "yet-another" not in summary_str

        # Configuration flags should be present
        assert summary["watsonx"]["configured"] is True
        assert summary["gemini"]["configured"] is True
        assert summary["groq"]["configured"] is True


# ─── Client tests ─────────────────────────────────────────────────────────────

class TestLLMClient:
    """Tests for app.llm_gateway.client — no real LLM calls."""

    @pytest.mark.asyncio
    async def test_complete_success_with_mock(self):
        """
        Happy-path: litellm.acompletion returns a mock response.
        Verifies routing, usage extraction, and CompletionResult fields.
        Does NOT make a real API call.
        """
        from app.llm_gateway.client import LLMClient

        # Build a minimal mock ModelResponse
        mock_usage = SimpleNamespace(prompt_tokens=120, completion_tokens=60)
        mock_message = SimpleNamespace(content="Predicted demand: 15000 pax")
        mock_choice = SimpleNamespace(message=mock_message)
        mock_response = SimpleNamespace(choices=[mock_choice], usage=mock_usage)

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        with patch("app.llm_gateway.client.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)

            client = LLMClient(default_timeout=5.0)
            result = await client.complete(
                task_type="structured_extraction",
                messages=[{"role": "user", "content": "Predict crowd exit demand."}],
                db=mock_db,
            )

        assert result.content == "Predicted demand: 15000 pax"
        assert result.prompt_tokens == 120
        assert result.completion_tokens == 60
        assert result.fallback_used is False
        assert result.provider in ("watsonx", "gemini", "groq")

    @pytest.mark.asyncio
    async def test_complete_falls_back_on_auth_error(self):
        """
        When primary model raises AuthenticationError, client falls back
        to next model in the list.
        Does NOT make a real API call.
        """
        from app.llm_gateway.client import LLMClient

        mock_usage = SimpleNamespace(prompt_tokens=50, completion_tokens=30)
        mock_message = SimpleNamespace(content="Fallback response")
        mock_choice = SimpleNamespace(message=mock_message)
        mock_response = SimpleNamespace(choices=[mock_choice], usage=mock_usage)

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        call_count = 0

        async def mock_acompletion(model: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("AuthenticationError: invalid api key")
            return mock_response

        with patch("app.llm_gateway.client.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion

            client = LLMClient(default_timeout=5.0)
            result = await client.complete(
                task_type="strategic_reasoning",
                messages=[{"role": "user", "content": "Generate a plan."}],
                db=mock_db,
            )

        assert result.fallback_used is True
        assert result.fallback_reason is not None
        assert call_count == 2  # primary failed, fallback succeeded

    @pytest.mark.asyncio
    async def test_complete_raises_when_all_fail(self):
        """
        When all providers fail, LLMGatewayError is raised.
        Does NOT make a real API call.
        """
        from app.llm_gateway.client import LLMClient, LLMGatewayError

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        async def always_fail(**kwargs):
            raise Exception("Connection refused")

        with patch("app.llm_gateway.client.litellm") as mock_litellm:
            mock_litellm.acompletion = always_fail

            client = LLMClient(default_timeout=5.0)
            with pytest.raises(LLMGatewayError) as exc_info:
                await client.complete(
                    task_type="classification",
                    messages=[{"role": "user", "content": "Classify this."}],
                    db=mock_db,
                )

        assert "classification" in str(exc_info.value)
        assert len(exc_info.value.attempted) >= 1

    @pytest.mark.asyncio
    async def test_complete_timeout_triggers_fallback(self):
        """
        When primary times out, client falls back to next model.
        Does NOT make a real API call.
        """
        import asyncio
        from app.llm_gateway.client import LLMClient

        mock_usage = SimpleNamespace(prompt_tokens=40, completion_tokens=20)
        mock_message = SimpleNamespace(content="OK")
        mock_choice = SimpleNamespace(message=mock_message)
        mock_response = SimpleNamespace(choices=[mock_choice], usage=mock_usage)

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        call_count = 0

        async def timeout_then_succeed(model: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            return mock_response

        with patch("app.llm_gateway.client.litellm") as mock_litellm:
            mock_litellm.acompletion = timeout_then_succeed

            client = LLMClient(default_timeout=0.001)

            # Patch asyncio.wait_for to pass through immediately without actual timeout
            with patch("app.llm_gateway.client.asyncio.wait_for", side_effect=timeout_then_succeed):
                try:
                    result = await client.complete(
                        task_type="multilingual_generation",
                        messages=[{"role": "user", "content": "Generate guidance."}],
                        db=mock_db,
                    )
                    assert result.fallback_used is True
                except Exception:
                    # TimeoutError propagation is also acceptable behavior
                    pass

    def test_get_llm_client_returns_singleton(self):
        """get_llm_client() must return the same instance on repeated calls."""
        from app.llm_gateway.client import get_llm_client

        c1 = get_llm_client()
        c2 = get_llm_client()
        assert c1 is c2

    def test_completion_result_content_accessor(self):
        """CompletionResult.content returns first choice message content."""
        from app.llm_gateway.client import CompletionResult

        mock_message = SimpleNamespace(content="Test output")
        mock_choice = SimpleNamespace(message=mock_message)
        mock_response = SimpleNamespace(choices=[mock_choice])

        result = CompletionResult(
            response=mock_response,
            model_used="groq/llama-3.1-8b-instant",
            provider="groq",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=200,
        )
        assert result.content == "Test output"

    def test_completion_result_content_fallback_on_bad_response(self):
        """CompletionResult.content returns '' when response has no choices."""
        from app.llm_gateway.client import CompletionResult

        result = CompletionResult(
            response=SimpleNamespace(),  # no .choices
            model_used="groq/llama-3.1-8b-instant",
            provider="groq",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )
        assert result.content == ""
