"""
Test script to verify bot module can be imported and initialized.
This does NOT actually run the bot, just checks imports and basic structure.
"""

import os
import sys
from pathlib import Path

# Set dummy env variables for testing
os.environ["OPENROUTER_API_KEY"] = "test-key"
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_CHAT_ID"] = "123456"
os.environ["CAREER_AGENT_MODEL"] = "openai/gpt-4o-mini"
os.environ["JUDGE_AGENT_MODEL"] = "google/gemini-2.0-flash-001"
os.environ["APPROVAL_THRESHOLD"] = "4.0"
os.environ["CHROMADB_PERSIST_DIR"] = "./data/chromadb"


def test_bot_imports():
    """Test that bot module can be imported."""
    print("Testing bot module imports...")

    # Import the bot module
    from bot import telegram_bot
    print("✅ bot.telegram_bot imported")

    # Check that CareerAssistantBot class exists
    assert hasattr(telegram_bot, "CareerAssistantBot")
    print("✅ CareerAssistantBot class exists")

    # Check that the class has required methods
    required_methods = [
        "_is_admin",
        "start_command",
        "reply_command",
        "show_cv_command",
        "status_command",
        "handle_employer_message",
        "_generate_with_revision_loop",
        "_send_intervention_alert",
        "_register_handlers",
        "run",
    ]

    for method in required_methods:
        assert hasattr(telegram_bot.CareerAssistantBot, method)
        print(f"✅ CareerAssistantBot.{method} exists")

    print("\n✅ All bot import tests passed!")


if __name__ == "__main__":
    test_bot_imports()
