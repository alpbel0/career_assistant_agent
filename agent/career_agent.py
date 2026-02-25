"""
Career Agent — Employer mesajlarına profesyonel cevap üreten ana agent.

Bu modül:
- OpenRouter API ile async iletişim kurar
- Conversation history yönetir (history.json)
- CV context'i (RAG/static) prompt'a enjekte eder
- Retry logic + graceful fallback sağlar
- /reply komutu için casual→professional dönüşüm yapar
"""

import os
import asyncio
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx

# Add parent directory to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))
from tools.cv_context import get_cv_context


class CareerAgent:
    """
    Career Agent — employer messages generate professional responses.

    Uses OpenRouter API with GPT-4o-mini for response generation.
    Maintains conversation history per employer in history.json.
    """

    def __init__(self):
        """Initialize CareerAgent with configuration."""
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        self.model = os.getenv("CAREER_AGENT_MODEL", "openai/gpt-4o-mini")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.history_path = Path("data/history.json")
        self.max_retries = 3
        self.prompt_path = Path("agent/prompts/career_prompt.txt")

        # Ensure history.json exists
        self._ensure_history_file()

    def _ensure_history_file(self) -> None:
        """Create history.json if it doesn't exist."""
        if not self.history_path.exists():
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                "version": "1.0",
                "conversations": {}
            }
            self.history_path.write_text(
                json.dumps(initial_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def _load_system_prompt(self) -> str:
        """Load the system prompt from career_prompt.txt."""
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        # Fallback prompt if file doesn't exist
        return """You are a professional Career Assistant representing Yiğitalp Bel.
Provide helpful, accurate, and professional responses based on the CV context.
Only use information from the CV — do not invent details.
Be professional yet approachable, confident but humble."""

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Async OpenRouter API call with retry logic.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response

        Returns:
            Dict with:
                - content: str (generated response)
                - tokens_used: int (total tokens consumed)
                - raw_response: dict (full API response for debugging)
        """
        fallback_message = "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com/alpbel0/career_assistant_agent",
                            "X-Title": "Career Assistant AI Agent",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                        }
                    )
                    response.raise_for_status()
                    data = response.json()

                    content = data["choices"][0]["message"]["content"]
                    tokens_used = data.get("usage", {}).get("total_tokens", 0)

                    return {
                        "content": content,
                        "tokens_used": tokens_used,
                        "raw_response": data
                    }

            except httpx.HTTPStatusError as e:
                # Server errors — retry with backoff
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    print(f"Server error {e.response.status_code}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                # Client errors — don't retry
                print(f"HTTP error: {e.response.status_code} - {e.response.text}")
                return {
                    "content": fallback_message,
                    "tokens_used": 0,
                    "raw_response": {"error": str(e)}
                }

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Timeout, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                print("Request timed out after all retries")
                return {
                    "content": fallback_message,
                    "tokens_used": 0,
                    "raw_response": {"error": "timeout"}
                }

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Unexpected error: {e}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                print(f"Unexpected error after all retries: {e}")
                return {
                    "content": fallback_message,
                    "tokens_used": 0,
                    "raw_response": {"error": str(e)}
                }

        # Should not reach here, but graceful fallback
        return {
            "content": fallback_message,
            "tokens_used": 0,
            "raw_response": {"error": "max_retries_exceeded"}
        }

    def _load_history(self, employer_id: str) -> List[Dict[str, Any]]:
        """
        Load conversation history from history.json.

        Args:
            employer_id: Unique employer identifier (Telegram ID/username)

        Returns:
            List of message dicts with 'role', 'content', 'timestamp'
        """
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            conversations = data.get("conversations", {})
            employer_data = conversations.get(employer_id, {})
            return employer_data.get("messages", [])
        except Exception as e:
            print(f"Error loading history: {e}")
            return []

    def _save_history(
        self,
        employer_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Save message to history.json.

        Args:
            employer_id: Unique employer identifier
            role: Message role ('employer' or 'assistant')
            content: Message content
        """
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))

            if "conversations" not in data:
                data["conversations"] = {}

            if employer_id not in data["conversations"]:
                data["conversations"][employer_id] = {"messages": []}

            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().timestamp()
            }

            data["conversations"][employer_id]["messages"].append(message)

            self.history_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Error saving history: {e}")

    def _format_conversation_history(
        self,
        messages: List[Dict[str, Any]],
        max_history: int = 10
    ) -> str:
        """
        Format conversation history for prompt.

        Args:
            messages: List of message dicts
            max_history: Maximum number of recent messages to include

        Returns:
            Formatted string of conversation history
        """
        if not messages:
            return "No previous conversation."

        # Get recent messages
        recent = messages[-max_history:] if len(messages) > max_history else messages

        formatted = []
        for msg in recent:
            role_label = "Employer" if msg["role"] == "employer" else "Yiğitalp (Assistant)"
            formatted.append(f"{role_label}: {msg['content']}")

        return "\n".join(formatted)

    async def generate_response(
        self,
        employer_id: str,
        employer_message: str,
        cv_query: str = "",
        feedback: str = ""
    ) -> Dict[str, Any]:
        """
        Generate professional response to employer message.

        Args:
            employer_id: Unique employer identifier (Telegram ID/username)
            employer_message: The message from employer
            cv_query: Optional query for RAG context retrieval
            feedback: Optional feedback from Judge Agent for revision

        Returns:
            Dict with:
                - response: str (generated response)
                - raw_llm_response: str (for debugging)
                - tokens_used: int
                - employer_message_saved: bool
        """
        # Save employer message to history (only on first call, not revisions)
        if not feedback:
            self._save_history(employer_id, "employer", employer_message)

        # Load conversation history
        history = self._load_history(employer_id)
        formatted_history = self._format_conversation_history(history)

        # Get CV context (RAG or static)
        cv_query = cv_query or employer_message
        cv_context = get_cv_context(cv_query)

        # Load and format system prompt
        system_template = self._load_system_prompt()

        # Add feedback to system prompt if this is a revision
        feedback_section = ""
        if feedback:
            feedback_section = f"\n\nREVISION FEEDBACK (improve based on this):\n{feedback}\n\nGenerate a revised response addressing the feedback above."

        system_prompt = system_template.format(
            cv_context=cv_context,
            conversation_history=formatted_history,
            employer_message=employer_message
        ) + feedback_section

        # Call LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": employer_message}
        ]

        llm_result = await self._call_llm(messages)

        # Save assistant response to history (only on approved responses)
        response = llm_result["content"]
        if not feedback:
            self._save_history(employer_id, "assistant", response)

        return {
            "response": response,
            "raw_llm_response": llm_result["raw_response"],
            "tokens_used": llm_result["tokens_used"],
            "employer_message_saved": not feedback  # Only saved if not a revision
        }

    async def professionalize_instruction(
        self,
        casual_instruction: str
    ) -> Dict[str, Any]:
        """
        Convert casual human instruction to professional response.
        Used for /reply command.

        Args:
            casual_instruction: Casual instruction from admin
                e.g., "Tell them I'm available next week"

        Returns:
            Dict with:
                - response: str (professional version)
                - raw_llm_response: str (for debugging)
                - tokens_used: int
        """
        system_prompt = """You are writing on behalf of a job candidate who is communicating with a potential employer.

The candidate's owner has given you a casual note describing what they want to say to the employer.
Your job is to turn that note into a polished, professional message — written in FIRST PERSON as if the candidate is speaking directly to the employer.

Rules:
- Write as the candidate (first person: "I", "Ben" etc.)
- The message should be addressed TO the employer, not to the person giving instructions
- Keep the original meaning, make it professional and courteous
- Match the language of the instruction (Turkish instruction → Turkish output, English → English)
- If you use a salutation, use "Sayın Yetkili" — NEVER write "Sayın [İşverenin Adı]" or any placeholder
- If you add a closing signature, use "Yiğitalp BEL" — NEVER write "Ben" or "Saygılarımla, Ben"
- Output only the final message — no explanations, no labels, no intro"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Casual note from candidate: {casual_instruction}"}
        ]

        llm_result = await self._call_llm(messages)

        return {
            "response": llm_result["content"],
            "raw_llm_response": llm_result["raw_response"],
            "tokens_used": llm_result["tokens_used"]
        }

    async def classify_message(self, employer_message: str) -> Dict[str, Any]:
        """
        LLM tabanlı intervention sınıflandırıcısı.
        Keyword yerine LLM karar verir — farklı ifadeler de yakalanır.

        Returns:
            {"needs_intervention": bool, "reason": str | None}
            reason: salary_negotiation | legal_question | ambiguous_offer | off_topic | None
        """
        system_prompt = """You are an intervention classifier for a career assistant chatbot.

A career assistant bot automatically responds to employer messages on behalf of a job candidate.
Some messages require HUMAN intervention and should NOT be handled automatically.

Intervention is needed when:
- salary_negotiation: Message discusses salary, compensation, pay, equity, benefits amounts, bonuses
- legal_question: Message mentions contracts, NDA, legal clauses, agreements to sign, terms
- ambiguous_offer: Message contains a job offer that needs clarification or acceptance/rejection decision
- off_topic: Message is spam, completely unrelated to recruitment, or seems malicious

Normal questions about experience, skills, availability, interview scheduling, job details = NO intervention.

Return ONLY valid JSON, no markdown, no explanation:
{"needs_intervention": true, "reason": "salary_negotiation"}
or
{"needs_intervention": false, "reason": null}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Employer message: {employer_message}"}
        ]

        result = await self._call_llm(messages, max_tokens=60)
        content = result["content"].strip()

        try:
            # Markdown kod bloğunu temizle
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content.strip())
            return {
                "needs_intervention": bool(parsed.get("needs_intervention", False)),
                "reason": parsed.get("reason") or None
            }
        except (json.JSONDecodeError, KeyError, IndexError):
            # Parse hatası → güvenli varsayılan
            return {"needs_intervention": False, "reason": None}

    def get_conversation_summary(self, employer_id: str) -> Dict[str, Any]:
        """
        Get summary of conversation with employer.

        Args:
            employer_id: Unique employer identifier

        Returns:
            Dict with message count, last message time, etc.
        """
        messages = self._load_history(employer_id)

        if not messages:
            return {
                "employer_id": employer_id,
                "message_count": 0,
                "last_message": None
            }

        return {
            "employer_id": employer_id,
            "message_count": len(messages),
            "last_message": {
                "role": messages[-1]["role"],
                "timestamp": messages[-1]["timestamp"],
                "preview": messages[-1]["content"][:100] + "..."
            }
        }
