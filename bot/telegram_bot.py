"""
Telegram Bot — Career Assistant AI Agent

Bu modül:
- Telegram üzerinden işveren mesajlarını alır
- Career Agent ile cevap üretir
- Judge Agent ile değerlendirir
- Revizyon loop'u yapar (max 3 iterasyon)
- İnsan müdahalesi gerektiğinde admin'e bildirir
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from agent.career_agent import CareerAgent
from agent.evaluator_agent import EvaluatorAgent
from tools.cv_context import get_cv_context

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Constants
MAX_REVISION_ITERATIONS = 3


class CareerAssistantBot:
    """
    Telegram Bot for Career Assistant AI Agent.

    Features:
    - Handles employer messages
    - Generates responses using CareerAgent
    - Evaluates responses using EvaluatorAgent
    - Revision loop with feedback (max 3 iterations)
    - Human intervention detection
    - Admin-only commands
    """

    def __init__(self):
        """Initialize the bot with agents and configuration."""
        # Environment variables
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.admin_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        if not self.admin_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")

        self.admin_chat_id = int(self.admin_chat_id)

        # Initialize agents
        self.career_agent = CareerAgent()
        self.evaluator_agent = EvaluatorAgent()

        # Track active employer conversations
        # Key: employer_id, Value: dict with metadata
        self.active_conversations: Dict[str, Dict[str, Any]] = {}

        # Statistics
        self.stats = {
            "start_time": datetime.now().isoformat(),
            "messages_processed": 0,
            "responses_approved": 0,
            "interventions_triggered": 0,
            "revision_loops": 0,
        }

        logger.info("CareerAssistantBot initialized")

    def _is_admin(self, update: Update) -> bool:
        """
        Check if the user is the admin.

        Args:
            update: Telegram update object

        Returns:
            True if user is admin, False otherwise
        """
        if not update.effective_user:
            return False

        user_id = update.effective_user.id
        return user_id == self.admin_chat_id

    def _get_employer_id(self, update: Update) -> str:
        """
        Get a unique identifier for the employer.

        Args:
            update: Telegram update object

        Returns:
            Unique employer ID string
        """
        user = update.effective_user
        if user.username:
            return f"@{user.username}"
        return str(user.id)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /start command — welcome message.

        Only admin can use this command.
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu botu kullanma yetkiniz yok."
            )
            return

        welcome_message = (
            "👋 *Career Assistant Bot'a Hoş Geldiniz!*\n\n"
            "Bu bot, işveren mesajlarına otomatik ve profesyonel cevaplar üretir.\n\n"
            "*Kullanılabilir Komutlar:*\n"
            "/status — Bot durumunu göster\n"
            "/show_cv — CV'yi görüntüle\n"
            "/reply <mesaj> — Casual→Professional dönüşüm\n\n"
            "Bot herhangi bir mesajı aldığında otomatik olarak cevap üretir."
        )

        await update.message.reply_text(welcome_message, parse_mode="Markdown")

    async def reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /reply command — convert casual instruction to professional response.

        Usage: /reply tell them I'm available next week
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        if not context.args or len(" ".join(context.args).strip()) == 0:
            await update.message.reply_text(
                "ℹ️ Kullanım: /reply <mesaj>\n\n"
                "Örnek: /reply tell them I'm available next week"
            )
            return

        casual_instruction = " ".join(context.args)

        await update.message.reply_text(
            "⏳ Profesyonel versiyon hazırlanıyor..."
        )

        try:
            result = await self.career_agent.professionalize_instruction(
                casual_instruction
            )

            response_text = (
                "✅ *Professional Cevap:*\n\n"
                f"{result['response']}"
            )

            await update.message.reply_text(response_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in /reply command: {e}")
            await update.message.reply_text(
                f"❌ Hata oluştu: {str(e)}"
            )

    async def show_cv_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /show_cv command — send CV as text and as document.
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        cv_path = Path("data/cv.txt")

        if not cv_path.exists():
            await update.message.reply_text("❌ CV dosyası bulunamadı.")
            return

        try:
            # Send as text preview
            cv_content = cv_path.read_text(encoding="utf-8")
            cv_preview = cv_content[:500]
            if len(cv_content) > 500:
                cv_preview += "\n\n... (dosya devam ediyor)"

            await update.message.reply_text(
                f"📄 *CV Önizleme:*\n\n```\n{cv_preview}\n```",
                parse_mode="Markdown"
            )

            # Send as document
            await update.message.reply_document(
                document=cv_path.open("rb"),
                filename="cv.txt",
                caption="📄 CV Dosyası"
            )

        except Exception as e:
            logger.error(f"Error in /show_cv command: {e}")
            await update.message.reply_text(f"❌ CV gönderilemedi: {str(e)}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /status command — show bot status and statistics.
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        # Calculate uptime
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = datetime.now() - start_time
        uptime_str = str(uptime).split(".")[0]  # Remove microseconds

        # Get approval rate
        if self.stats["messages_processed"] > 0:
            approval_rate = (
                self.stats["responses_approved"] / self.stats["messages_processed"]
            ) * 100
        else:
            approval_rate = 0.0

        status_text = (
            "📊 *Bot Durumu*\n\n"
            f"⏱️ Çalışma Süresi: `{uptime_str}`\n"
            f"💬 İşlenen Mesaj: `{self.stats['messages_processed']}`\n"
            f"✅ Onaylanan Cevap: `{self.stats['responses_approved']}`\n"
            f"⚠️ Intervention: `{self.stats['interventions_triggered']}`\n"
            f"🔄 Revizyon Döngüsü: `{self.stats['revision_loops']}`\n"
            f"📈 Onay Oranı: `%{approval_rate:.1f}`\n\n"
            f"🤖 *Career Agent:* `{os.getenv('CAREER_AGENT_MODEL', 'gpt-4o-mini')}`\n"
            f"⚖️ *Judge Agent:* `{os.getenv('JUDGE_AGENT_MODEL', 'gemini-2.0-flash')}`\n"
            f"🎯 *Threshold:* `{os.getenv('APPROVAL_THRESHOLD', '4.0')}`"
        )

        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def _generate_with_revision_loop(
        self,
        employer_message: str,
        employer_id: str
    ) -> Dict[str, Any]:
        """
        Generate response with revision loop (max 3 iterations).

        Args:
            employer_message: The message from employer
            employer_id: Unique employer identifier

        Returns:
            Dict with:
                - response: str (final approved response or last draft)
                - evaluation: dict (final evaluation)
                - iterations: int (number of iterations used)
                - success: bool (whether response was approved)
                - intervention_triggered: bool
                - intervention_reason: str | None
        """
        cv_context = get_cv_context(employer_message)
        feedback = ""
        iterations = 0
        last_evaluation = None
        last_response = None

        for iteration in range(1, MAX_REVISION_ITERATIONS + 1):
            iterations = iteration
            logger.info(f"Iteration {iteration}/{MAX_REVISION_ITERATIONS}")

            # Generate response with feedback (if any)
            generation_result = await self.career_agent.generate_response(
                employer_id=employer_id,
                employer_message=employer_message,
                cv_query=employer_message,
                feedback=feedback
            )

            last_response = generation_result["response"]

            # Evaluate the response
            evaluation = await self.evaluator_agent.evaluate(
                employer_message=employer_message,
                response=last_response,
                cv_context=cv_context
            )

            last_evaluation = evaluation

            logger.info(
                f"Iteration {iteration}: Score={evaluation['overall_score']}, "
                f"Approved={evaluation['is_approved']}, "
                f"Intervention={evaluation['trigger_human_intervention']}"
            )

            # Check for intervention first
            if evaluation.get("trigger_human_intervention"):
                return {
                    "response": last_response,
                    "evaluation": evaluation,
                    "iterations": iterations,
                    "success": False,
                    "intervention_triggered": True,
                    "intervention_reason": evaluation.get("intervention_reason"),
                    "feedback": evaluation.get("feedback", "")
                }

            # Check if approved
            if evaluation.get("is_approved"):
                # Save the approved response to history
                self.career_agent._save_history(
                    employer_id, "assistant", last_response
                )
                return {
                    "response": last_response,
                    "evaluation": evaluation,
                    "iterations": iterations,
                    "success": True,
                    "intervention_triggered": False,
                    "intervention_reason": None,
                    "feedback": evaluation.get("feedback", "")
                }

            # Not approved - prepare feedback for next iteration
            feedback = evaluation.get("feedback", "Improve the response.")
            logger.info(f"Response not approved. Feedback: {feedback}")

            self.stats["revision_loops"] += 1

        # Max iterations reached without approval
        return {
            "response": last_response,
            "evaluation": last_evaluation,
            "iterations": iterations,
            "success": False,
            "intervention_triggered": False,
            "intervention_reason": None,
            "feedback": last_evaluation.get("feedback", "") if last_evaluation else ""
        }

    async def _send_intervention_alert(
        self,
        update: Update,
        reason: str,
        message: str,
        draft_response: str
    ) -> None:
        """
        Send intervention alert to admin.

        Args:
            update: Telegram update object
            reason: Intervention reason
            message: Original employer message
            draft_response: Generated draft response
        """
        reason_emojis = {
            "salary_negotiation": "💰",
            "legal_question": "⚖️",
            "out_of_domain": "🔬",
            "ambiguous_offer": "🌫️",
            "off_topic": "🚫",
        }

        emoji = reason_emojis.get(reason, "⚠️")

        alert_text = (
            f"{emoji} *INTERVENTION GEREKLİ*\n\n"
            f"*Sebep:* `{reason}`\n\n"
            f"*İşveren Mesajı:*\n{message}\n\n"
            f"*Taslak Cevap:*\n{draft_response}\n\n"
            "⚠️ Lütfen bu durumu manuel olarak yönetin."
        )

        await update.message.reply_text(alert_text, parse_mode="Markdown")

    async def handle_employer_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle incoming employer messages (non-command messages).

        This is the main flow:
        1. Receive message
        2. Generate response with revision loop
        3. Check for intervention
        4. If approved, show the response
        """
        # Reject messages from non-admin users
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu botu kullanma yetkiniz yok."
            )
            return

        if not update.message or not update.message.text:
            return

        employer_message = update.message.text
        employer_id = self._get_employer_id(update)

        # Skip empty messages
        if not employer_message.strip():
            return

        self.stats["messages_processed"] += 1

        logger.info(f"Processing message from {employer_id}: {employer_message[:50]}...")

        # Send typing indicator
        await update.message.chat.send_action("typing")

        try:
            # Generate response with revision loop
            result = await self._generate_with_revision_loop(
                employer_message=employer_message,
                employer_id=employer_id
            )

            # Handle intervention
            if result["intervention_triggered"]:
                self.stats["interventions_triggered"] += 1
                await self._send_intervention_alert(
                    update=update,
                    reason=result.get("intervention_reason", "unknown"),
                    message=employer_message,
                    draft_response=result["response"]
                )
                return

            # Handle successful generation
            if result["success"]:
                self.stats["responses_approved"] += 1

                eval_data = result["evaluation"]
                response_text = (
                    "✅ *Cevap Onaylandı*\n\n"
                    f"* skor:* `{eval_data['overall_score']}`\n"
                    f"*T:* `{eval_data['truthfulness_score']}` "
                    f"*R:* `{eval_data['robustness_score']}` "
                    f"*H:* `{eval_data['helpfulness_score']}` "
                    f"*T:* `{eval_data['tone_score']}`\n"
                    f"*İterasyon:* `{result['iterations']}`\n\n"
                    f"*Cevap:*\n{result['response']}"
                )

                await update.message.reply_text(response_text, parse_mode="Markdown")
            else:
                # Max iterations reached without approval
                response_text = (
                    "⚠️ *Cevap Onaylanamadı*\n\n"
                    f"Maksimum iterasyon sayısı ({MAX_REVISION_ITERATIONS}) "
                    f"ulaşıldı ancak onay alınamadı.\n\n"
                    f"*Son skor:* `{result['evaluation']['overall_score']}`\n"
                    f"*Feedback:* {result['evaluation'].get('feedback', 'Yok')}\n\n"
                    f"*Taslak Cevap:*\n{result['response']}"
                )

                await update.message.reply_text(response_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Mesaj işlenirken hata oluştu: {str(e)}\n\n"
                "Lütfen daha sonra tekrar deneyin."
            )

    def _register_handlers(self, application: Application) -> None:
        """
        Register all command and message handlers.

        Args:
            application: Telegram Application instance
        """
        # Command handlers (admin only)
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("reply", self.reply_command))
        application.add_handler(CommandHandler("show_cv", self.show_cv_command))
        application.add_handler(CommandHandler("status", self.status_command))

        # Message handler for employer messages
        # Filters out commands and handles everything else
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_employer_message
            )
        )

        # Error handler
        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Log errors caused by updates."""
            logger.error(
                f"Update {update} caused error {context.error}",
                exc_info=context.error
            )

        application.add_error_handler(error_handler)

    async def _set_bot_commands(self, application: Application) -> None:
        """Set bot commands for better UX in Telegram."""
        commands = [
            BotCommand("start", "Botu başlat"),
            ("status", "Bot durumunu göster"),
            ("show_cv", "CV'yi görüntüle"),
            ("reply", "Casual→Professional dönüşüm"),
        ]

        try:
            await application.bot.set_my_commands(commands)
            logger.info("Bot commands registered")
        except Exception as e:
            logger.error(f"Failed to set bot commands: {e}")

    def run(self) -> None:
        """Start the bot."""
        try:
            # Create application
            application = Application.builder().token(self.bot_token).build()

            # Register handlers
            self._register_handlers(application)

            # Set bot commands (async, need to run in context)
            async def setup_and_run():
                await self._set_bot_commands(application)
                logger.info("Bot started. Polling for messages...")

                # Run the application with polling
                await application.run_polling(
                    drop_pending_updates=True,
                    allowed_updates=["message"]
                )

            # Run the bot
            import asyncio
            asyncio.run(setup_and_run())

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
            raise


def main():
    """Entry point for running the bot."""
    try:
        bot = CareerAssistantBot()
        bot.run()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file.")
        sys.exit(1)
    except Exception as e:
        print(f"Bot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
