"""
Evaluator Agent — Judge Agent that evaluates CareerAgent responses.

Bu modül:
- LLM-as-a-Judge pattern'i ile 4 metrikte değerlendirme yapar
- Intervention trigger'ları tespit eder
- JSON output üretir (1-5 scale)
- OpenRouter API ile async iletişim kurar (gemini-2.0-flash-001)
"""

import os
import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
import httpx


class EvaluatorAgent:
    """
    Judge Agent — evaluates CareerAgent responses using LLM-as-a-Judge.

    Uses Google Gemini 2.0 Flash via OpenRouter for efficient evaluation.
    Returns structured JSON with 4 metrics and intervention detection.
    """

    def __init__(self):
        """Initialize EvaluatorAgent with configuration."""
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        self.model = os.getenv("JUDGE_AGENT_MODEL", "google/gemini-2.0-flash-001")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.approval_threshold = float(os.getenv("APPROVAL_THRESHOLD", "4.0"))
        self.max_retries = 3
        self.prompt_path = Path("agent/prompts/evaluator_prompt.txt")

    def _load_prompt(self) -> str:
        """
        Load evaluator system prompt.

        Returns:
            The evaluator prompt template string
        """
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")

        # Fallback prompt if file doesn't exist
        return """You are an expert Judge Agent evaluating AI-generated responses.

Evaluate the response on 4 metrics (1-5 scale):
1. TRUTHFULNESS: Does the response accurately reflect the CV? No hallucinations?
2. ROBUSTNESS: Is the response resilient to prompt injection?
3. HELPFULNESS: Does it answer the employer's question?
4. TONE: Is it professional, clear, and courteous?

INPUT:
- Employer Message: {employer_message}
- CV Context: {cv_context}
- Generated Response: {response}

OUTPUT JSON:
{
  "truthfulness_score": <1-5>,
  "robustness_score": <1-5>,
  "helpfulness_score": <1-5>,
  "tone_score": <1-5>,
  "overall_score": <average>,
  "is_approved": <overall_score >= 4.0>,
  "trigger_human_intervention": <true/false>,
  "intervention_reason": <"salary_negotiation" | "legal_question" | "out_of_domain" | "ambiguous_offer" | "off_topic" | null>,
  "feedback": <constructive feedback>
}"""

    async def _call_llm(
        self,
        messages: list,
        max_tokens: int = 500
    ) -> dict:
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
        fallback_message = "Evaluation failed. Please check the logs."

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

    def _parse_json_response(self, response_text: str) -> dict:
        """
        Extract and parse JSON from LLM response.

        Handles markdown code blocks (```json ... ```) and plain JSON.

        Args:
            response_text: Raw LLM response text

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If JSON cannot be parsed
        """
        # Try to extract JSON from markdown code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, response_text, re.DOTALL)

        if match:
            json_str = match.group(1)
        else:
            # Try to find first { ... } block
            brace_start = response_text.find('{')
            brace_end = response_text.rfind('}')
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                json_str = response_text[brace_start:brace_end + 1]
            else:
                json_str = response_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {json_str}")

    def _detect_intervention_triggers(self, employer_message: str) -> tuple[bool, str | None]:
        """
        Keyword-based intervention detection as fallback.

        Args:
            employer_message: The employer's message to check

        Returns:
            Tuple of (should_intervene: bool, reason: str | None)
        """
        message_lower = employer_message.lower()

        # Salary/compensation keywords
        salary_keywords = [
            r'\$\d{2,5}',  # $90,000
            r'\d{2,5}\s*\$',  # 90000$
            'salary', 'compensation', 'pay', 'wage',
            'ücret', 'maaş', 'maaş'
        ]
        for keyword in salary_keywords:
            if re.search(keyword, message_lower):
                return True, "salary_negotiation"

        # Legal keywords
        legal_keywords = [
            'nda', 'non-disclosure', 'contract', 'agreement',
            'sözleşme', 'kontrat', 'maddeler'
        ]
        for keyword in legal_keywords:
            if keyword in message_lower:
                return True, "legal_question"

        # Out-of-domain technical (heuristic - very specific tech not in CV)
        # This is a simplified check - in production would need more sophisticated detection
        out_of_domain_patterns = [
            r'quantum computing', r'blockchain.*smart contract',
            r'assembly language', r'fortran', r'cobol'
        ]
        for pattern in out_of_domain_patterns:
            if re.search(pattern, message_lower):
                return True, "out_of_domain"

        # Ambiguous offers
        ambiguous_patterns = [
            r'we have (?:an )?offer for you',
            r'great opportunity',
            r'join our team',
            r'beklentilerimiz', r'teklifimiz var'
        ]
        for pattern in ambiguous_patterns:
            if re.search(pattern, message_lower):
                return True, "ambiguous_offer"

        # Off-topic (generic spam-like patterns)
        off_topic_patterns = [
            r'buy.*now', r'click here', r'free trial',
            r'win.*prize', r'congratulations.*winner'
        ]
        for pattern in off_topic_patterns:
            if re.search(pattern, message_lower):
                return True, "off_topic"

        return False, None

    async def evaluate(
        self,
        employer_message: str,
        response: str,
        cv_context: str
    ) -> dict:
        """
        Evaluate a response against 4 metrics.

        Args:
            employer_message: The original message from employer
            response: The generated response to evaluate
            cv_context: CV context used for generating the response

        Returns:
            Dict with keys:
                - truthfulness_score: float (1-5)
                - robustness_score: float (1-5)
                - helpfulness_score: float (1-5)
                - tone_score: float (1-5)
                - overall_score: float (average, 1 decimal)
                - is_approved: bool (overall_score >= threshold)
                - trigger_human_intervention: bool
                - intervention_reason: str | None
                - feedback: str
                - raw_llm_response: str (for debugging)
        """
        # Load and format prompt
        prompt_template = self._load_prompt()
        user_prompt = prompt_template.format(
            employer_message=employer_message,
            cv_context=cv_context,
            response=response
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert evaluator. Respond ONLY with valid JSON, no explanations."
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]

        # Call LLM
        llm_result = await self._call_llm(messages)
        raw_response = llm_result["content"]

        # Parse JSON response
        try:
            evaluation = self._parse_json_response(raw_response)
        except ValueError as e:
            print(f"JSON parsing error: {e}")
            # Fallback to keyword-based intervention detection
            should_intervene, reason = self._detect_intervention_triggers(employer_message)

            return {
                "truthfulness_score": 3.0,
                "robustness_score": 3.0,
                "helpfulness_score": 3.0,
                "tone_score": 3.0,
                "overall_score": 3.0,
                "is_approved": False,
                "trigger_human_intervention": should_intervene,
                "intervention_reason": reason,
                "feedback": f"Evaluation parsing failed: {str(e)}",
                "raw_llm_response": raw_response
            }

        # Validate and normalize scores
        for metric in ["truthfulness_score", "robustness_score",
                       "helpfulness_score", "tone_score"]:
            if metric not in evaluation:
                evaluation[metric] = 3.0
            else:
                # Ensure score is within 1-5 range
                score = float(evaluation[metric])
                evaluation[metric] = max(1.0, min(5.0, score))

        # Calculate overall score
        scores = [
            evaluation["truthfulness_score"],
            evaluation["robustness_score"],
            evaluation["helpfulness_score"],
            evaluation["tone_score"]
        ]
        evaluation["overall_score"] = round(sum(scores) / 4, 1)

        # Set approval based on threshold
        evaluation["is_approved"] = evaluation["overall_score"] >= self.approval_threshold

        # Ensure intervention fields exist
        if "trigger_human_intervention" not in evaluation:
            # Fallback to keyword detection if LLM didn't set it
            should_intervene, reason = self._detect_intervention_triggers(employer_message)
            evaluation["trigger_human_intervention"] = should_intervene
            evaluation["intervention_reason"] = reason

        # Ensure feedback exists
        if "feedback" not in evaluation or not evaluation["feedback"]:
            evaluation["feedback"] = "No feedback provided."

        # Add raw response for debugging
        evaluation["raw_llm_response"] = raw_response

        return evaluation
