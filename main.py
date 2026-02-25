import asyncio
import logging
import os
import re
from dotenv import load_dotenv

from database import DatabaseManager
from scraper import HotdealScraper
from scorer import HotdealScorer
from bot import TelegramBot

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fetch_and_process_deals(db: DatabaseManager, scraper: HotdealScraper, scorer: HotdealScorer, bot: TelegramBot):
    logger.info("5개 핫딜 사이트 통합 크롤링 시작...")
    
    deals = await scraper.scrape_all()
    new_updates = False
    
    for deal in deals:
        url = deal['url']
        title = deal['title']
        source = deal['source']
        
        if await db.is_url_exists(url):
            continue
            
        logger.info(f"신규 발견 [{source}]: {title}")
        
        # 정규식을 활용하여 제목 내에서 가격(원/숫자) 데이터 추출 시도
        prices = re.findall(r'\d{1,3}(?:,\d{3})*(?:원)?', title)
        final_price = int(prices[-1].replace(',', '').replace('원', '')) if prices else 0
        
        # 상세 댓글 크롤링 생략으로 인한 제목 기반 단일 분석
        analysis = await scorer.analyze_deal(title, final_price, 0, "목록 기반 수집으로 상세 댓글 생략")
        
        if analysis['total_score'] >= 60:
            deal_id = await db.insert_deal(url, title, final_price, analysis['total_score'], 'NEW')
            
            if deal_id:
                message_text = f"🚨 **[핫딜] {title}**\n\n" \
                               f"* **정보 출처:** {source} ([게시글 링크]({url}))\n" \
                               f"* **주의:** 봇에 의해 자동 수집된 정보입니다. 정확하지 않거나 틀릴 수 있는 정보이므로 구매 전 반드시 실제 조건을 확인하십시오.\n\n" \
                               f"💰 **추정 결제가:** **{final_price}원**\n\n" \
                               f"📝 **AI 핫딜 브리핑**\n{analysis['briefing']}\n\n" \
                               f"📊 **종합 핫딜 지수: {analysis['total_score']}점**"
                
                await bot.send_hotdeal_alert(deal_id, message_text)
                new_updates = True
        else:
            await db.insert_deal(url, title, final_price, analysis['total_score'], 'DISCARDED')

    if not new_updates:
        await bot.send_system_message("업데이트 내역이 없습니다.")

async def scheduler_loop(db, scraper, scorer, bot):
    while True:
        try:
            await fetch_and_process_deals(db, scraper, scorer, bot)
        except Exception as e:
            logger.error(f"스케줄러 에러: {e}")
        
        logger.info("다음 수집 대기 중 (5분)...")
        await asyncio.sleep(300)

async def main():
    db = DatabaseManager()
    await db.init_db()
    
    scraper = HotdealScraper()
    scorer = HotdealScorer()
    bot = TelegramBot(db)
    
    if hasattr(bot, 'bot'):
        asyncio.create_task(scheduler_loop(db, scraper, scorer, bot))
        logger.info("시스템 작동 시작...")
        await bot.start_polling()

if __name__ == "__main__":
    asyncio.run(main())