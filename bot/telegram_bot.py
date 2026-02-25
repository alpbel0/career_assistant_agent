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

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from agent.career_agent import CareerAgent
from agent.evaluator_agent import EvaluatorAgent
from tools.cv_context import get_cv_context, check_cv_relevance
from tools.logger import log_interaction

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

        # Bot instance (will be set when handlers are registered)
        self.bot = None

        # Track active employer conversations
        # Key: employer_id, Value: dict with metadata
        self.active_conversations: Dict[str, Dict[str, Any]] = {}

        # Track pending interventions (employer_id -> data)
        self.pending_interventions: Dict[str, Dict[str, Any]] = {}

        # Track admin's drafted responses
        self.admin_drafts: Dict[str, str] = {}

        # Track last employer who sent a message (for /reply without intervention)
        self.last_employer_id: str = None
        self.last_employer_user_id: int = None

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
            "/reply <mesaj> — Casual→Professional dönüşüm\n"
            "/update_cv — CV dosyasını güncelle (.txt yükle)\n"
            "/add_info <metin> — CV'ye bilgi ekle\n"
            "/remove_info <metin> — CV'den bilgi sil\n\n"
            "Bot herhangi bir mesajı aldığında otomatik olarak cevap üretir."
        )

        await update.message.reply_text(welcome_message, parse_mode="Markdown")

    async def reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /reply command — convert casual instruction to professional response.

        Usage: /reply tell them I'm available next week

        If there's a pending intervention waiting for custom response,
        sends it directly to the employer.
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        # Check if waiting for custom response for a specific employer
        for employer_id, draft in list(self.admin_drafts.items()):
            if draft.startswith("waiting_"):
                # This is the intervention waiting for response
                casual_instruction = " ".join(context.args) if context.args else ""

                if not casual_instruction:
                    await update.message.reply_text("⚠️ Lütfen mesaj yaz:\n\nÖrnek: /reply müsait olduğumu söyle")
                    return

                # Professionalize and show preview with buttons
                try:
                    await update.message.reply_text("⏳ Profesyonel versiyon hazırlanıyor...")

                    result = await self.career_agent.professionalize_instruction(
                        casual_instruction
                    )
                    professional_response = result['response']

                    # Store the professionalized text (ready to send)
                    self.admin_drafts[employer_id] = professional_response

                    # Show preview with Send / Rewrite buttons
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Gönder", callback_data=f"confirm_send_{employer_id}"),
                            InlineKeyboardButton("✏️ Tekrar Yaz", callback_data=f"retry_custom_{employer_id}"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await update.message.reply_text(
                        f"📝 *Profesyonel Cevap Önizleme:*\n\n{professional_response}\n\n"
                        f"👇 Ne yapmak istersin?",
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                    return
                except Exception as e:
                    logger.error(f"Error in /reply command: {e}")
                    await update.message.reply_text(f"❌ Hata: {str(e)}")
                    return

        # Normal /reply flow (no pending intervention)
        if not context.args or len(" ".join(context.args).strip()) == 0:
            if self.pending_interventions:
                pending_list = "\n".join([
                    f"• `{emp_id}` ({inv['reason']})"
                    for emp_id, inv in self.pending_interventions.items()
                ])
                await update.message.reply_text(
                    f"⏳ *Bekleyen Intervention'lar:*\n\n{pending_list}\n\n"
                    "Cevap göndermek için butona tıkla.",
                    parse_mode="Markdown"
                )
            else:
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

            professional_response = result['response']

            if self.last_employer_id and self.last_employer_user_id:
                # Store for direct send
                self.admin_drafts[f"direct_{self.last_employer_id}"] = professional_response
                keyboard = [[
                    InlineKeyboardButton("✅ Gönder", callback_data=f"direct_send_{self.last_employer_id}"),
                    InlineKeyboardButton("🚫 Sadece Önizle", callback_data="discard_preview"),
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"✅ *Professional Cevap:*\n\n{professional_response}\n\n"
                    f"📤 *Gönderilecek:* `{self.last_employer_id}`",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    f"✅ *Professional Cevap:*\n\n{professional_response}",
                    parse_mode="Markdown"
                )

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

    async def update_cv_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /update_cv command — Update CV by uploading a new .txt file.

        Usage: Send /update_cv with a document attachment
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        # Check if a document is attached
        if not update.message.document:
            await update.message.reply_text(
                "ℹ️ Kullanım: /update_cv komutunu bir `.txt` dosyası ile birlikte gönderin.\n\n"
                "Örnek:\n/update_cv\n[CV.txt dosyasını ekleyin]"
            )
            return

        document = update.message.document

        # Check file extension
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text(
                "⚠️ Lütfen sadece `.txt` formatında dosya yükleyin."
            )
            return

        try:
            # Send processing message
            await update.message.reply_text("⏳ CV güncelleniyor...")

            # Download the file
            file = await document.get_file()
            cv_path = Path("data/cv.txt")

            # Create backup of old CV
            if cv_path.exists():
                backup_path = Path("data/cv_backup.txt")
                backup_path.write_text(cv_path.read_text(encoding="utf-8"), encoding="utf-8")

            # Download and save new CV
            import io
            content = await file.download_as_bytearray()
            cv_path.write_bytes(content)

            # Re-index CV in ChromaDB
            try:
                from tools.index_cv import index_cv
                index_cv()
                chroma_status = "✅ ChromaDB'ye yeniden指数lendi."
            except Exception as e:
                logger.error(f"ChromaDB re-index error: {e}")
                chroma_status = f"⚠️ ChromaDB指数leme hatası: {str(e)}"

            # Get new CV stats
            new_content = cv_path.read_text(encoding="utf-8")
            char_count = len(new_content)
            word_count = len(new_content.split())

            response_text = (
                "✅ *CV Güncellendi!*\n\n"
                f"📁 Dosya: `{document.file_name}`\n"
                f"📝 Karakter: `{char_count}`\n"
                f"📊 Kelime: `{word_count}`\n\n"
                f"{chroma_status}\n\n"
                f"💾 Yedek: `data/cv_backup.txt`"
            )

            await update.message.reply_text(response_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in /update_cv command: {e}")
            await update.message.reply_text(f"❌ CV güncellenemedi: {str(e)}")

    async def add_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /add_info command — Append new information to CV.

        Usage: /add_info Yeni bir proje: X projesinde yaptım...
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        if not context.args or len(" ".join(context.args).strip()) == 0:
            await update.message.reply_text(
                "ℹ️ Kullanım: /add_info <metin>\n\n"
                "Örnek: /add_info Yeni sertifika: AWS Solutions Architect"
            )
            return

        new_info = " ".join(context.args)
        cv_path = Path("data/cv.txt")

        if not cv_path.exists():
            await update.message.reply_text("❌ CV dosyası bulunamadı.")
            return

        try:
            # Read current CV
            current_content = cv_path.read_text(encoding="utf-8")

            # Create backup
            backup_path = Path("data/cv_backup.txt")
            backup_path.write_text(current_content, encoding="utf-8")

            # Append new info
            updated_content = current_content.rstrip() + "\n\n" + new_info

            # Save updated CV
            cv_path.write_text(updated_content, encoding="utf-8")

            # Re-index CV in ChromaDB
            try:
                from tools.index_cv import index_cv
                index_cv()
                chroma_status = "\n✅ ChromaDB'ye yeniden指数lendi."
            except Exception as e:
                logger.error(f"ChromaDB re-index error: {e}")
                chroma_status = f"\n⚠️ ChromaDB指数leme hatası: {str(e)}"

            await update.message.reply_text(
                f"✅ *CV'ye Bilgi Eklendi*\n\n"
                f"Eklenen bilgi:\n`{new_info[:200]}{'...' if len(new_info) > 200 else ''}`\n"
                f"Yeni CV uzunluğu: `{len(updated_content)}` karakter{chroma_status}",
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Error in /add_info command: {e}")
            await update.message.reply_text(f"❌ Bilgi eklenemedi: {str(e)}")

    async def remove_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /remove_info command — Remove specific line or text from CV.

        Usage: /remove_info <aranan_metin>
        Removes lines containing the searched text.
        """
        if not self._is_admin(update):
            await update.message.reply_text(
                "⛔ Bu komutu kullanma yetkiniz yok."
            )
            return

        if not context.args or len(" ".join(context.args).strip()) == 0:
            await update.message.reply_text(
                "ℹ️ Kullanım: /remove_info <aranan_metin>\n\n"
                "Örnek: /remove_info Eski proje\n\n"
                "Bu komut, aranan metni içeren satırları siler."
            )
            return

        search_text = " ".join(context.args).lower()
        cv_path = Path("data/cv.txt")

        if not cv_path.exists():
            await update.message.reply_text("❌ CV dosyası bulunamadı.")
            return

        try:
            # Read current CV
            current_content = cv_path.read_text(encoding="utf-8")
            lines = current_content.split('\n')

            # Find and remove lines containing search text
            original_count = len(lines)
            filtered_lines = [line for line in lines if search_text not in line.lower()]
            removed_count = original_count - len(filtered_lines)

            if removed_count == 0:
                await update.message.reply_text(
                    f"⚠️ '{search_text}' içeren satır bulunamadı."
                )
                return

            # Create backup
            backup_path = Path("data/cv_backup.txt")
            backup_path.write_text(current_content, encoding="utf-8")

            # Save updated CV
            updated_content = '\n'.join(filtered_lines)
            cv_path.write_text(updated_content, encoding="utf-8")

            # Re-index CV in ChromaDB
            try:
                from tools.index_cv import index_cv
                index_cv()
                chroma_status = "\n✅ ChromaDB'ye yeniden指数lendi."
            except Exception as e:
                logger.error(f"ChromaDB re-index error: {e}")
                chroma_status = f"\n⚠️ ChromaDB指数leme hatası: {str(e)}"

            await update.message.reply_text(
                f"✅ *CV'den Bilgi Silindi*\n\n"
                f"Aranan: `{search_text}`\n"
                f"Silinen satır: `{removed_count}`\n"
                f"Yeni CV uzunluğu: `{len(updated_content)}` karakter{chroma_status}",
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Error in /remove_info command: {e}")
            await update.message.reply_text(f"❌ Bilgi silinemedi: {str(e)}")

    async def _classify_intervention(self, message: str) -> tuple[bool, str]:
        """
        LLM tabanlı intervention sınıflandırıcı.
        Farklı ifadeler ve dolaylı anlatımlar da yakalanır.

        Returns:
            (should_intervene: bool, reason: str | None)
        """
        result = await self.career_agent.classify_message(message)
        return result["needs_intervention"], result["reason"]

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
        Send intervention alert to admin and acknowledgment to employer.

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
        employer_id = self._get_employer_id(update)
        employer_user_id = update.effective_user.id

        # Store intervention state
        self.pending_interventions[employer_id] = {
            "employer_user_id": employer_user_id,
            "message": message,
            "draft_response": draft_response,
            "reason": reason,
        }

        # Send acknowledgment to employer
        await update.message.reply_text(
            "Mesajınız alındı. En kısa sürede size dönüş yapacağım. İyi günler!"
        )

        # Send detailed alert to admin with inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Taslağı Gönder", callback_data=f"send_draft_{employer_id}"),
                InlineKeyboardButton("✏️ Kendi Yaz", callback_data=f"custom_{employer_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        alert_text = (
            f"{emoji} *INTERVENTION — Onay Bekliyor*\n\n"
            f"*Kaynak:* `{employer_id}` (ID: {employer_user_id})\n"
            f"*Sebep:* `{reason}`\n\n"
            f"*İşveren Mesajı:*\n{message}\n\n"
            f"*Taslak Cevap:*\n{draft_response}\n\n"
            "👇 Ne yapmak istersin?"
        )

        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=alert_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send intervention alert to admin: {e}")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle callback queries from inline keyboard buttons.

        Actions:
        - send_draft_<employer_id>: Send the draft response to employer
        - custom_<employer_id>: Prompt admin to write custom response
        """
        query = update.callback_query
        if not query:
            return

        await query.answer()  # Acknowledge the callback

        # Security check - only admin can handle callbacks
        if query.from_user.id != self.admin_chat_id:
            await query.edit_message_text("⚠️ Bu işlem için yetkiniz yok.")
            return

        callback_data = query.data
        if not callback_data:
            return

        logger.info(f"🔘 Callback received: {callback_data}")

        try:
            if callback_data.startswith("send_draft_"):
                employer_id = callback_data.replace("send_draft_", "")
                intervention = self.pending_interventions.get(employer_id)

                if not intervention:
                    await query.edit_message_text(f"⚠️ İşlem bulunamadı veya zaman aşımına uğradı.")
                    return

                # Send draft to employer
                employer_user_id = intervention["employer_user_id"]
                draft_response = intervention["draft_response"]

                try:
                    await self.bot.send_message(
                        chat_id=employer_user_id,
                        text=draft_response
                    )
                    await query.edit_message_text(
                        f"✅ Taslak cevap `{employer_id}` adresine gönderildi.",
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ Draft sent to employer {employer_id}")
                except Exception as e:
                    logger.error(f"Failed to send draft to employer: {e}")
                    await query.edit_message_text(f"❌ Gönderim başarısız: {e}")

                # Clean up
                self.pending_interventions.pop(employer_id, None)

            elif callback_data.startswith("custom_"):
                employer_id = callback_data.replace("custom_", "")
                intervention = self.pending_interventions.get(employer_id)

                if not intervention:
                    await query.edit_message_text(f"⚠️ İşlem bulunamadı veya zaman aşımına uğradı.")
                    return

                # Store marker for custom reply - admin will use /reply command
                # The intervention stays in pending_interventions, we just mark it as waiting
                self.admin_drafts[employer_id] = f"waiting_for_custom_response"

                await query.edit_message_text(
                    f"✏️ Özel cevap yazma modu.\n\n"
                    f"Şimdi `/reply <mesaj>` komutunu kullanarak kendi cevabınızı yazın.\n"
                    f"Cevapınız `{employer_id}` adresine gönderilecek.",
                    parse_mode="Markdown"
                )
                logger.info(f"✏️ Admin prompted for custom response to {employer_id}")

            elif callback_data.startswith("confirm_send_"):
                employer_id = callback_data.replace("confirm_send_", "")
                intervention = self.pending_interventions.get(employer_id)
                professional_response = self.admin_drafts.get(employer_id)

                if not intervention or not professional_response:
                    await query.edit_message_text("⚠️ İşlem bulunamadı veya zaman aşımına uğradı.")
                    return

                employer_user_id = intervention["employer_user_id"]

                try:
                    await context.bot.send_message(
                        chat_id=employer_user_id,
                        text=professional_response
                    )
                    await query.edit_message_text(
                        f"✅ Mesaj `{employer_id}` adresine gönderildi:\n\n{professional_response}",
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ Custom response sent to employer {employer_id}")
                except Exception as e:
                    logger.error(f"Failed to send custom response to employer: {e}")
                    await query.edit_message_text(f"❌ Gönderim başarısız: {e}")

                # Clean up
                self.pending_interventions.pop(employer_id, None)
                self.admin_drafts.pop(employer_id, None)

            elif callback_data.startswith("direct_send_"):
                employer_id = callback_data.replace("direct_send_", "")
                professional_response = self.admin_drafts.get(f"direct_{employer_id}")

                if not professional_response or self.last_employer_user_id is None:
                    await query.edit_message_text("⚠️ İşlem bulunamadı veya zaman aşımına uğradı.")
                    return

                try:
                    await context.bot.send_message(
                        chat_id=self.last_employer_user_id,
                        text=professional_response
                    )
                    await query.edit_message_text(
                        f"✅ Mesaj `{employer_id}` adresine gönderildi:\n\n{professional_response}",
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ Direct reply sent to employer {employer_id}")
                except Exception as e:
                    logger.error(f"Failed to send direct reply: {e}")
                    await query.edit_message_text(f"❌ Gönderim başarısız: {e}")

                self.admin_drafts.pop(f"direct_{employer_id}", None)

            elif callback_data == "discard_preview":
                await query.edit_message_text("🗑️ Önizleme silindi.")

            elif callback_data.startswith("retry_custom_"):
                employer_id = callback_data.replace("retry_custom_", "")

                if employer_id not in self.pending_interventions:
                    await query.edit_message_text("⚠️ İşlem bulunamadı veya zaman aşımına uğradı.")
                    return

                # Reset to waiting state
                self.admin_drafts[employer_id] = "waiting_for_custom_response"

                await query.edit_message_text(
                    f"✏️ Tekrar yaz modu.\n\n"
                    f"`/reply <mesaj>` komutunu kullanarak yeni cevabını yaz.\n"
                    f"Cevap `{employer_id}` adresine gönderilecek.",
                    parse_mode="Markdown"
                )
                logger.info(f"✏️ Admin prompted to retry custom response for {employer_id}")

            else:
                await query.edit_message_text("⚠️ Bilinmeyen işlem.")

        except Exception as e:
            logger.error(f"Error handling callback query: {e}", exc_info=True)
            try:
                await query.edit_message_text(f"❌ İşlem hatası: {e}")
            except Exception:
                pass

    async def handle_employer_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle incoming employer messages (non-command messages).

        This is the main flow:
        1. Receive message (from anyone - employer messages)
        2. Generate response with revision loop
        3. Check for intervention
        4. If approved, show the response

        NOTE: This accepts messages from ANYONE (simulating employers).
        Only admin commands are restricted.
        """
        if not update.effective_user:
            logger.warning("Received message without effective_user")
            return

        user_id = update.effective_user.id
        username = update.effective_user.username or "no_username"
        is_admin = self._is_admin(update)

        logger.info(f"📨 Message from user_id={user_id}, username={username}, is_admin={is_admin}")

        if not update.message or not update.message.text:
            return

        employer_message = update.message.text
        employer_id = self._get_employer_id(update)

        # Skip empty messages
        if not employer_message.strip():
            return

        self.stats["messages_processed"] += 1

        # Track last employer for /reply command
        if not is_admin:
            self.last_employer_id = employer_id
            self.last_employer_user_id = user_id

        logger.info(f"Processing message from {employer_id}: {employer_message[:50]}...")

        # ─ Admin'e yeni mesaj bildirimi (sadece işverenden geliyorsa)
        if not is_admin:
            try:
                await self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=(
                        f"📨 *Yeni İşveren Mesajı*\n\n"
                        f"*Gönderen:* `{employer_id}`\n"
                        f"*Mesaj:* {employer_message[:200]}"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send new-message notification to admin: {e}")

        # Send typing indicator
        await update.message.chat.send_action("typing")

        try:
            # ─────────────────────────────────────────────────────────────────
            # PRE-CHECK 1: LLM tabanlı intervention sınıflandırması
            # ─────────────────────────────────────────────────────────────────
            should_intervene, intervention_reason = await self._classify_intervention(employer_message)
            if should_intervene:
                logger.info(f"🚨 Pre-check intervention: {intervention_reason}")
                self.stats["interventions_triggered"] += 1
                try:
                    log_interaction(
                        employer_id=employer_id,
                        employer_message=employer_message,
                        draft_response="",
                        evaluation=None,
                        final_response="",
                        is_approved=False,
                        iterations=0,
                        intervention_triggered=True,
                        intervention_reason=intervention_reason,
                    )
                except Exception as log_err:
                    logger.error(f"Logging failed (non-critical): {log_err}")
                await self._send_intervention_alert(
                    update=update,
                    reason=intervention_reason,
                    message=employer_message,
                    draft_response=""
                )
                return

            # ─────────────────────────────────────────────────────────────────
            # MAIN FLOW: CV'de bilgi var → üret → değerlendir → gönder
            # ─────────────────────────────────────────────────────────────────
            result = await self._generate_with_revision_loop(
                employer_message=employer_message,
                employer_id=employer_id
            )

            # PRE-CHECK 3: Agent konu hakkında bilgisi yoksa → admin
            if result.get("response", "").strip() == "[UNCERTAIN]":
                logger.info("🚨 Agent returned [UNCERTAIN] → routing to admin")
                self.stats["interventions_triggered"] += 1
                try:
                    log_interaction(
                        employer_id=employer_id,
                        employer_message=employer_message,
                        draft_response="[UNCERTAIN]",
                        evaluation=None,
                        final_response="",
                        is_approved=False,
                        iterations=result.get("iterations", 0),
                        intervention_triggered=True,
                        intervention_reason="out_of_domain",
                    )
                except Exception as log_err:
                    logger.error(f"Logging failed (non-critical): {log_err}")
                await self._send_intervention_alert(
                    update=update,
                    reason="out_of_domain",
                    message=employer_message,
                    draft_response=""
                )
                return

            # Log interaction
            try:
                log_interaction(
                    employer_id=employer_id,
                    employer_message=employer_message,
                    draft_response=result.get("response", ""),
                    evaluation=result.get("evaluation"),
                    final_response=result.get("response", ""),
                    is_approved=result.get("success", False),
                    iterations=result.get("iterations", 0),
                    intervention_triggered=False,
                    intervention_reason=None,
                )
            except Exception as log_err:
                logger.error(f"Logging failed (non-critical): {log_err}")

            # Handle successful generation
            if result["success"]:
                self.stats["responses_approved"] += 1

                if is_admin:
                    eval_data = result["evaluation"]
                    response_text = (
                        "✅ *Cevap Onaylandı*\n\n"
                        f"*Skor:* `{eval_data['overall_score']}`\n"
                        f"*T:* `{eval_data['truthfulness_score']}` "
                        f"*R:* `{eval_data['robustness_score']}` "
                        f"*H:* `{eval_data['helpfulness_score']}` "
                        f"*To:* `{eval_data['tone_score']}`\n"
                        f"*İterasyon:* `{result['iterations']}`\n\n"
                        f"*Cevap:*\n{result['response']}"
                    )
                    await update.message.reply_text(response_text, parse_mode="Markdown")
                else:
                    # İşverene cevabı gönder
                    await update.message.reply_text(result["response"])

                    # Admin'e onay bildirimi gönder
                    try:
                        eval_data = result["evaluation"]
                        await self.bot.send_message(
                            chat_id=self.admin_chat_id,
                            text=(
                                f"✅ *Cevap Onaylandı & Gönderildi*\n\n"
                                f"*İşveren:* `{employer_id}`\n"
                                f"*Skor:* `{eval_data['overall_score']}` "
                                f"(T:`{eval_data['truthfulness_score']}` "
                                f"R:`{eval_data['robustness_score']}` "
                                f"H:`{eval_data['helpfulness_score']}` "
                                f"To:`{eval_data['tone_score']}`)"
                                f"\n*İterasyon:* `{result['iterations']}`\n\n"
                                f"*Gönderilen Cevap:*\n{result['response'][:300]}"
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send approval notification to admin: {e}")
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
        # Store bot instance for sending messages
        self.bot = application.bot

        # Command handlers (admin only)
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("reply", self.reply_command))
        application.add_handler(CommandHandler("show_cv", self.show_cv_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("update_cv", self.update_cv_command))
        application.add_handler(CommandHandler("add_info", self.add_info_command))
        application.add_handler(CommandHandler("remove_info", self.remove_info_command))

        # Message handler for employer messages
        # Filters out commands and handles everything else
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_employer_message
            )
        )

        # Callback query handler for inline keyboards
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))

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
            ("update_cv", "CV dosyasını güncelle"),
            ("add_info", "CV'ye bilgi ekle"),
            ("remove_info", "CV'den bilgi sil"),
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

            # Add post_init handler to set commands after bot starts
            async def post_init(application: Application) -> None:
                try:
                    await self._set_bot_commands(application)
                except Exception as e:
                    logger.error(f"Failed to set bot commands: {e}")

            application.post_init = post_init

            # Run the bot
            logger.info("Bot started. Polling for messages...")
            application.run_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )

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
