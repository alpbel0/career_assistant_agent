"""
Unit tests for CareerAgent.

Tests cover:
- Response generation
- Conversation history management
- Professionalize instruction (/reply command)
- Error handling and retry logic
"""

import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.career_agent import CareerAgent


@pytest.fixture
def mock_env_vars():
    """Set required environment variables for testing."""
    os.environ["OPENROUTER_API_KEY"] = "test_key_123"
    os.environ["CAREER_AGENT_MODEL"] = "openai/gpt-4o-mini"
    yield
    # Cleanup
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ.pop("CAREER_AGENT_MODEL", None)


@pytest.fixture
def temp_history_file(tmp_path, mock_env_vars):
    """Create a temporary history.json file for testing."""
    # Temporarily override history path
    original_path = Path("data/history.json")

    # Create temp history file
    temp_history = tmp_path / "history.json"
    temp_history.write_text(
        '{"version": "1.0", "conversations": {}}',
        encoding="utf-8"
    )

    # Patch the history path in CareerAgent
    with patch.object(CareerAgent, '__init__', lambda self: _init_with_custom_history(self, temp_history)):
        yield temp_history


def _init_with_custom_history(agent, custom_path):
    """Custom init for testing with custom history path."""
    agent.api_key = os.getenv("OPENROUTER_API_KEY")
    agent.model = os.getenv("CAREER_AGENT_MODEL", "openai/gpt-4o-mini")
    agent.base_url = "https://openrouter.ai/api/v1/chat/completions"
    agent.history_path = custom_path
    agent.max_retries = 3
    agent.prompt_path = Path("agent/prompts/career_prompt.txt")


@pytest.fixture
def agent(mock_env_vars, tmp_path):
    """Create a CareerAgent instance for testing."""
    temp_history = tmp_path / "history.json"
    temp_history.write_text(
        '{"version": "1.0", "conversations": {}}',
        encoding="utf-8"
    )

    agent_instance = CareerAgent()

    # Override history path
    agent_instance.history_path = temp_history

    return agent_instance


@pytest.mark.asyncio
async def test_agent_initialization(mock_env_vars):
    """Test that CareerAgent initializes correctly."""
    agent = CareerAgent()
    assert agent.api_key == "test_key_123"
    assert agent.model == "openai/gpt-4o-mini"
    assert agent.base_url == "https://openrouter.ai/api/v1/chat/completions"
    assert agent.max_retries == 3


@pytest.mark.asyncio
async def test_generate_response_success(agent):
    """Test basic response generation with successful API call."""
    mock_response = {
        "choices": [{
            "message": {
                "content": "Thank you for the interview invitation. I would be happy to schedule a time to speak."
            }
        }],
        "usage": {
            "total_tokens": 150
        }
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.generate_response(
            employer_id="test_123",
            employer_message="We'd like to invite you for an interview.",
            cv_query="interview"
        )

        assert "response" in result
        assert len(result["response"]) > 0
        assert result["tokens_used"] == 150
        assert result["employer_message_saved"] is True


@pytest.mark.asyncio
async def test_conversation_history_persistence(agent):
    """Test that conversation history is maintained across messages."""
    mock_response_1 = {
        "choices": [{"message": {"content": "Hello! Thank you for reaching out."}}],
        "usage": {"total_tokens": 50}
    }

    mock_response_2 = {
        "choices": [{"message": {"content": "I'm available Monday or Tuesday next week."}}],
        "usage": {"total_tokens": 60}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_http_response)

        async def mock_json_side_effect(*args, **kwargs):
            # Return different responses based on call
            if mock_post.call_count == 1:
                mock_http_response.json = MagicMock(return_value=mock_response_1)
            else:
                mock_http_response.json = MagicMock(return_value=mock_response_2)
            return mock_http_response.json.return_value

        mock_http_response.json = MagicMock(side_effect=mock_json_side_effect)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        # First message
        await agent.generate_response(
            employer_id="test_history",
            employer_message="Hello, we'd like to schedule an interview.",
            cv_query=""
        )

        # Second message — should have context
        await agent.generate_response(
            employer_id="test_history",
            employer_message="What is your availability?",
            cv_query="availability"
        )

        # Verify history was saved
        history = agent._load_history("test_history")
        assert len(history) >= 4  # 2 employer + 2 assistant messages
        assert history[0]["role"] == "employer"
        assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_professionalize_instruction(agent):
    """Test /reply command functionality - casual to professional conversion."""
    mock_response = {
        "choices": [{
            "message": {
                "content": "I would be pleased to schedule an interview at your earliest convenience."
            }
        }],
        "usage": {"total_tokens": 80}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.professionalize_instruction(
            "Tell them I'm available next week"
        )

        assert "response" in result
        assert len(result["response"]) > 20
        assert result["tokens_used"] == 80


@pytest.mark.asyncio
async def test_api_retry_on_server_error(agent):
    """Test that retry logic works on server errors (500+)."""
    mock_response = {
        "choices": [{"message": {"content": "Success after retry"}}],
        "usage": {"total_tokens": 50}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.status_code = 500

        # First call fails, second succeeds
        call_count = [0]

        async def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                mock_http_response.status_code = 500
                raise Exception("Server error")
            else:
                mock_http_response.status_code = 200
                mock_http_response.json = MagicMock(return_value=mock_response)
                return mock_http_response

        mock_post_func = AsyncMock(side_effect=mock_post)
        mock_client.return_value.__aenter__.return_value.post = mock_post_func

        result = await agent.generate_response(
            employer_id="test_retry",
            employer_message="Test message",
            cv_query=""
        )

        assert call_count[0] > 1  # Should have retried


@pytest.mark.asyncio
async def test_graceful_fallback_on_failure(agent):
    """Test graceful fallback message when API completely fails."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(side_effect=Exception("Connection failed"))
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await agent.generate_response(
            employer_id="test_fallback",
            employer_message="Test message",
            cv_query=""
        )

        # Should return fallback message
        assert "response" in result
        assert "Üzgünüm" in result["response"] or "yanıt veremiyorum" in result["response"]


def test_load_history_empty(agent):
    """Test loading history when employer has no messages."""
    history = agent._load_history("nonexistent_employer")
    assert history == []


def test_format_conversation_history(agent):
    """Test formatting conversation history for prompt."""
    messages = [
        {"role": "employer", "content": "Hello", "timestamp": 12345},
        {"role": "assistant", "content": "Hi there!", "timestamp": 12346}
    ]

    formatted = agent._format_conversation_history(messages)

    assert "Employer: Hello" in formatted
    assert "Yiğitalp (Assistant): Hi there!" in formatted


def test_format_conversation_history_with_limit(agent):
    """Test that history limit is respected."""
    messages = [
        {"role": "employer", "content": f"Message {i}", "timestamp": i}
        for i in range(20)
    ]

    formatted = agent._format_conversation_history(messages, max_history=5)

    # Should only have last 5 messages
    assert formatted.count("Employer:") == 5


def test_conversation_summary(agent):
    """Test getting conversation summary."""
    # First, empty summary
    summary = agent.get_conversation_summary("new_employer")
    assert summary["message_count"] == 0
    assert summary["last_message"] is None

    # Add some messages
    agent._save_history("test_summary", "employer", "Hello!")
    agent._save_history("test_summary", "assistant", "Hi!")

    summary = agent.get_conversation_summary("test_summary")
    assert summary["message_count"] == 2
    assert summary["last_message"]["role"] == "assistant"


@pytest.mark.asyncio
async def test_system_prompt_loading(agent):
    """Test that system prompt is loaded correctly."""
    prompt = agent._load_system_prompt()
    assert "Career Assistant" in prompt or "professional" in prompt.lower()


@pytest.mark.asyncio
async def test_multiple_employers_separate_histories(agent):
    """Test that different employers have separate conversation histories."""
    mock_response = {
        "choices": [{"message": {"content": "Response"}}],
        "usage": {"total_tokens": 50}
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)

        mock_post = AsyncMock(return_value=mock_http_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        # Message from employer A
        await agent.generate_response(
            employer_id="employer_a",
            employer_message="Hello from A",
            cv_query=""
        )

        # Message from employer B
        await agent.generate_response(
            employer_id="employer_b",
            employer_message="Hello from B",
            cv_query=""
        )

        # Verify separate histories
        history_a = agent._load_history("employer_a")
        history_b = agent._load_history("employer_b")

        assert len(history_a) == 2  # employer + assistant
        assert len(history_b) == 2
        assert "from A" in history_a[0]["content"]
        assert "from B" in history_b[0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
