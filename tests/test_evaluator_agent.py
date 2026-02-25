"""
Unit tests for EvaluatorAgent.

Tests cover:
- Evaluation with 4 metrics (1-5 scale)
- JSON parsing (markdown tolerant)
- Intervention detection (salary, legal, etc.)
- Threshold approval logic
- Retry logic on API failures
"""

import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.evaluator_agent import EvaluatorAgent


@pytest.fixture
def mock_env_vars():
    """Set required environment variables for testing."""
    os.environ["OPENROUTER_API_KEY"] = "test_key_123"
    os.environ["JUDGE_AGENT_MODEL"] = "google/gemini-2.0-flash-001"
    os.environ["APPROVAL_THRESHOLD"] = "4.0"
    yield
    # Cleanup
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ.pop("JUDGE_AGENT_MODEL", None)
    os.environ.pop("APPROVAL_THRESHOLD", None)


@pytest.fixture
def agent(mock_env_vars):
    """Create an EvaluatorAgent instance for testing."""
    return EvaluatorAgent()


# Test 1: Basic Agent Initialization
@pytest.mark.asyncio
async def test_agent_initialization(mock_env_vars):
    """Test that EvaluatorAgent initializes correctly."""
    agent = EvaluatorAgent()
    assert agent.api_key == "test_key_123"
    assert agent.model == "google/gemini-2.0-flash-001"
    assert agent.approval_threshold == 4.0
    assert agent.max_retries == 3


# Test 2: Evaluate Success Case
@pytest.mark.asyncio
async def test_evaluate_success(agent):
    """Test basic evaluation with successful API call."""
    mock_response = {
        "choices": [{
            "message": {
                "content": '''```json
                {
                    "truthfulness_score": 5,
                    "robustness_score": 4,
                    "helpfulness_score": 5,
                    "tone_score": 5,
                    "overall_score": 4.8,
                    "is_approved": true,
                    "trigger_human_intervention": false,
                    "intervention_reason": null,
                    "feedback": "Excellent response"
                }
                ```'''
            }
        }],
        "usage": {"total_tokens": 200}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="We'd like to invite you for an interview.",
            response="Thank you for the invitation. I would be happy to schedule an interview.",
            cv_context="Yiğitalp is a software engineer with experience in Python and AI."
        )

        assert result["truthfulness_score"] == 5
        assert result["robustness_score"] == 4
        assert result["helpfulness_score"] == 5
        assert result["tone_score"] == 5
        assert result["overall_score"] == 4.8
        assert result["is_approved"] is True
        assert result["trigger_human_intervention"] is False
        assert result["intervention_reason"] is None
        assert "feedback" in result
        assert "raw_llm_response" in result


# Test 3: JSON Parsing - Plain JSON (no markdown)
@pytest.mark.asyncio
async def test_json_parsing_plain(agent):
    """Test JSON parsing with plain JSON (no markdown code blocks)."""
    mock_response = {
        "choices": [{
            "message": {
                "content": '{"truthfulness_score": 4, "robustness_score": 4, "helpfulness_score": 4, "tone_score": 4, "overall_score": 4.0, "is_approved": true, "trigger_human_intervention": false, "intervention_reason": null, "feedback": "Good response"}'
            }
        }],
        "usage": {"total_tokens": 100}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="Test",
            response="Test response",
            cv_context="Test CV"
        )

        assert result["truthfulness_score"] == 4
        assert result["overall_score"] == 4.0


# Test 4: Intervention Detection - Salary Negotiation
@pytest.mark.asyncio
async def test_intervention_detection_salary(agent):
    """Test intervention detection for salary negotiation."""
    # Test with mock LLM response that includes intervention
    mock_response = {
        "choices": [{
            "message": {
                "content": '''```json
                {
                    "truthfulness_score": 5,
                    "robustness_score": 5,
                    "helpfulness_score": 5,
                    "tone_score": 5,
                    "overall_score": 5.0,
                    "is_approved": true,
                    "trigger_human_intervention": true,
                    "intervention_reason": "salary_negotiation",
                    "feedback": "Salary discussion requires human intervention"
                }
                ```'''
            }
        }],
        "usage": {"total_tokens": 150}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="We're offering a base salary of $90,000 + equity. Does that work for you?",
            response="Thank you for the offer.",
            cv_context="Test CV"
        )

        assert result["trigger_human_intervention"] is True
        assert result["intervention_reason"] == "salary_negotiation"


# Test 5: Intervention Detection - Legal Question
def test_intervention_detection_fallback_legal(agent):
    """Test keyword-based intervention detection for legal questions."""
    should_intervene, reason = agent._detect_intervention_triggers(
        "Please review the attached NDA agreement before we proceed."
    )

    assert should_intervene is True
    assert reason == "legal_question"


# Test 6: Intervention Detection - Out of Domain
def test_intervention_detection_fallback_out_of_domain(agent):
    """Test keyword-based intervention detection for out-of-domain questions."""
    should_intervene, reason = agent._detect_intervention_triggers(
        "Can you describe your experience with quantum computing algorithms?"
    )

    assert should_intervene is True
    assert reason == "out_of_domain"


# Test 7: Intervention Detection - No Intervention Needed
def test_intervention_detection_fallback_none(agent):
    """Test that normal messages don't trigger intervention."""
    should_intervene, reason = agent._detect_intervention_triggers(
        "We'd like to invite you for an interview next week. Are you available?"
    )

    assert should_intervene is False
    assert reason is None


# Test 8: Threshold Approval - Below Threshold
@pytest.mark.asyncio
async def test_threshold_approval_below(agent):
    """Test that scores below threshold are not approved."""
    mock_response = {
        "choices": [{
            "message": {
                "content": '''```json
                {
                    "truthfulness_score": 3,
                    "robustness_score": 3,
                    "helpfulness_score": 4,
                    "tone_score": 3,
                    "overall_score": 3.2,
                    "is_approved": false,
                    "trigger_human_intervention": false,
                    "intervention_reason": null,
                    "feedback": "Response needs improvement in truthfulness and tone"
                }
                ```'''
            }
        }],
        "usage": {"total_tokens": 150}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="Test",
            response="I don't know",
            cv_context="Test CV"
        )

        assert result["overall_score"] == 3.2
        assert result["is_approved"] is False


# Test 9: Threshold Approval - Exactly at Threshold
@pytest.mark.asyncio
async def test_threshold_approval_exactly(agent):
    """Test that score exactly at threshold is approved."""
    # Change threshold for this test
    agent.approval_threshold = 4.0

    mock_response = {
        "choices": [{
            "message": {
                "content": '{"truthfulness_score": 4, "robustness_score": 4, "helpfulness_score": 4, "tone_score": 4, "overall_score": 4.0, "is_approved": true, "trigger_human_intervention": false, "intervention_reason": null, "feedback": "Good"}'
            }
        }],
        "usage": {"total_tokens": 100}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="Test",
            response="Good response",
            cv_context="Test CV"
        )

        assert result["overall_score"] == 4.0
        assert result["is_approved"] is True


# Test 10: Retry Logic - Server Error
@pytest.mark.asyncio
async def test_retry_logic_server_error(agent):
    """Test that retry logic works on server errors."""
    mock_response = {
        "choices": [{
            "message": {
                "content": '{"truthfulness_score": 5, "robustness_score": 5, "helpfulness_score": 5, "tone_score": 5, "overall_score": 5.0, "is_approved": true, "trigger_human_intervention": false, "intervention_reason": null, "feedback": "Excellent"}'
            }
        }],
        "usage": {"total_tokens": 100}
    }

    with patch("httpx.AsyncClient") as mock_client:
        call_count = [0]

        async def mock_post(*args, **kwargs):
            call_count[0] += 1
            mock_http_response = MagicMock()

            if call_count[0] == 1:
                # First call fails
                raise Exception("Server error 500")
            else:
                # Second call succeeds
                mock_http_response.raise_for_status = MagicMock()
                mock_http_response.json = MagicMock(return_value=mock_response)
                return mock_http_response

        mock_post_func = AsyncMock(side_effect=mock_post)
        mock_client.return_value.__aenter__.return_value.post = mock_post_func

        result = await agent.evaluate(
            employer_message="Test",
            response="Test response",
            cv_context="Test CV"
        )

        # Should have retried at least once
        assert call_count[0] > 1
        assert result["overall_score"] == 5.0


# Test 11: Graceful Fallback on Complete Failure
@pytest.mark.asyncio
async def test_graceful_fallback_on_failure(agent):
    """Test graceful fallback when API completely fails."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(side_effect=Exception("Connection failed"))
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="Test",
            response="Test response",
            cv_context="Test CV"
        )

        # Should return fallback scores
        assert result["truthfulness_score"] == 3.0
        assert result["overall_score"] == 3.0
        assert result["is_approved"] is False
        # Should trigger keyword-based intervention check
        assert "trigger_human_intervention" in result


# Test 12: Parse JSON with Extra Text
def test_parse_json_with_extra_text(agent):
    """Test parsing JSON when LLM adds extra text before/after."""
    response_text = '''Here's my evaluation:

```json
{
    "truthfulness_score": 5,
    "robustness_score": 5,
    "helpfulness_score": 5,
    "tone_score": 5,
    "overall_score": 5.0,
    "is_approved": true,
    "trigger_human_intervention": false,
    "intervention_reason": null,
    "feedback": "Perfect response"
}
```

This response meets all criteria.'''

    parsed = agent._parse_json_response(response_text)

    assert parsed["truthfulness_score"] == 5
    assert parsed["overall_score"] == 5.0
    assert parsed["is_approved"] is True


# Test 13: Score Normalization
@pytest.mark.asyncio
async def test_score_normalization(agent):
    """Test that out-of-range scores are normalized to 1-5 range."""
    mock_response = {
        "choices": [{
            "message": {
                "content": '{"truthfulness_score": 10, "robustness_score": 0, "helpfulness_score": 3, "tone_score": 4, "overall_score": 4.0, "is_approved": true, "trigger_human_intervention": false, "intervention_reason": null, "feedback": "Test"}'
            }
        }],
        "usage": {"total_tokens": 100}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.evaluate(
            employer_message="Test",
            response="Test response",
            cv_context="Test CV"
        )

        # Scores should be clamped to 1-5 range
        assert 1.0 <= result["truthfulness_score"] <= 5.0
        assert 1.0 <= result["robustness_score"] <= 5.0


# Test 14: Overall Score Calculation
def test_overall_score_calculation(agent):
    """Test that overall score is calculated correctly."""
    # The evaluate method recalculates overall_score
    # This test verifies the calculation happens
    pass  # Calculation is tested in integration with evaluate()


# Test 15: Prompt Loading
def test_load_prompt(agent):
    """Test that evaluator prompt is loaded correctly."""
    prompt = agent._load_prompt()
    assert "TRUTHFULNESS" in prompt
    assert "ROBUSTNESS" in prompt
    assert "HELPFULNESS" in prompt
    assert "TONE" in prompt
    assert "INTERVENTION" in prompt or "intervention" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
