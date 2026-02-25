import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import DatabaseManager

logger = logging.getLogger(__name__)

class TelegramBot:
    """텔레그램 메시지 발송 및 사용자 상호작용을 처리하는 비동기 클래스"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.admin_id = os.getenv("TELEGRAM_ADMIN_ID")
        self.db = db_manager
        
        if not self.token or not self.admin_id:
            logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_ID environment variable is missing.")
            return

        self.bot = Bot(token=self.token)
        self.dp = Dispatcher()
        self._register_handlers()

    def _register_handlers(self):
        """명령어 및 콜백 쿼리 핸들러 등록"""
        
        @self.dp.message(Command("pending"))
        async def cmd_pending(message: types.Message):
            # 관리자 계정이 아닌 경우 무시
            if str(message.from_user.id) != self.admin_id:
                return
            
            pending_deals = await self.db.get_pending_deals()
            if not pending_deals:
                await message.answer("보류 중인 핫딜이 없습니다.")
                return
                
            response_text = "⏳ **보류 중인 핫딜 목록**\n\n"
            for deal in pending_deals:
                response_text += f"- [{deal['title']}]({deal['url']}) (점수: {deal['total_score']})\n"
            
            await message.answer(response_text, parse_mode="Markdown", disable_web_page_preview=True)

        @self.dp.callback_query(F.data.startswith("status_"))
        async def process_status_callback(callback_query: types.CallbackQuery):
            """인라인 버튼 클릭 시 상태 업데이트 처리"""
            _, action, deal_id = callback_query.data.split("_")
            deal_id = int(deal_id)
            
            success = await self.db.update_status(deal_id, action)
            
            if success:
                status_text = "업로드 완료" if action == "UPLOADED" else "보류됨"
                await callback_query.answer(f"상태가 '{status_text}'(으)로 변경되었습니다.")
                
                # 버튼 제거
                await self.bot.edit_message_reply_markup(
                    chat_id=callback_query.message.chat.id,
                    message_id=callback_query.message.message_id,
                    reply_markup=None
                )
            else:
                await callback_query.answer("상태 업데이트에 실패했습니다. DB를 확인하십시오.", show_alert=True)

    async def send_hotdeal_alert(self, deal_id: int, message_text: str):
        """핫딜 알림 메시지 및 상태 변경 인라인 키보드 발송"""
        if not hasattr(self, 'bot'):
            return
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ 업로드 완료", callback_data=f"status_UPLOADED_{deal_id}"),
                InlineKeyboardButton(text="⏳ 보류", callback_data=f"status_PENDING_{deal_id}")
            ]
        ])
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Telegram send_message Error: {e}")

    async def send_system_message(self, text: str):
        """일반 텍스트 시스템 메시지 발송 (업데이트 없음 등)"""
        if not hasattr(self, 'bot'):
            return
        try:
            await self.bot.send_message(chat_id=self.admin_id, text=text)
        except Exception as e:
            logger.error(f"Telegram send_system_message Error: {e}")

    async def start_polling(self):
        """텔레그램 봇 폴링 루프 시작 (비동기) 및 기존 웹훅 삭제"""
        if hasattr(self, 'bot'):
            await self.bot.delete_webhook(drop_pending_updates=True)
            await self.dp.start_polling(self.bot)