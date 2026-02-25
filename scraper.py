from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class HotdealScraper:
    """다중 웹사이트 HTML 파싱 및 우회 수집 클래스"""
    
    def __init__(self):
        # 5개 사이트 태그 구조 설정 (사이트 개편 시 수정 필요)
        self.targets = {
            "FMKorea": {"url": "https://www.fmkorea.com/hotdeal", "item": "li.li", "title": "h3.title > a", "link": "h3.title > a", "prefix": "https://www.fmkorea.com"},
            "TheQoo": {"url": "https://theqoo.net/theqdeal", "item": "table.board-list tbody tr", "title": "td.title a", "link": "td.title a", "prefix": "https://theqoo.net"},
            "ArcaLive": {"url": "https://arca.live/b/hotdeal", "item": "a.vrow", "title": "span.title", "link": "", "prefix": "https://arca.live"},
            "Quasarzone": {"url": "https://quasarzone.com/bbs/qb_saleinfo", "item": "div.market-info-list table tbody tr", "title": "span.ellipsis-with-reply-cnt", "link": "a.subject-link", "prefix": "https://quasarzone.com"},
            "HotdealZip": {"url": "https://hotdeal.zip/", "item": "div.post-item", "title": "h3.post-title a", "link": "h3.post-title a", "prefix": ""}
        }

    async def fetch_html(self, url: str) -> str:
        try:
            # impersonate="chrome110" 옵션으로 실제 크롬 브라우저처럼 위장하여 Cloudflare 우회
            async with AsyncSession(impersonate="chrome110") as session:
                response = await session.get(url, timeout=15)
                if response.status_code == 200:
                    return response.text
                else:
                    logger.error(f"HTTP {response.status_code} 차단됨: {url}")
                    return ""
        except Exception as e:
            logger.error(f"통신 에러 {url}: {e}")
            return ""

    async def scrape_all(self) -> List[Dict[str, Any]]:
        all_deals = []
        for name, config in self.targets.items():
            html = await self.fetch_html(config["url"])
            if not html:
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select(config["item"])
            
            for item in items:
                try:
                    title_el = item.select_one(config["title"]) if config["title"] else item
                    link_el = item.select_one(config["link"]) if config["link"] else item
                    
                    if not title_el or not link_el:
                        continue
                        
                    title = title_el.text.strip()
                    raw_link = link_el.get('href', '')
                    if not raw_link or 'javascript' in raw_link:
                        continue
                        
                    link = config["prefix"] + raw_link if raw_link.startswith('/') else raw_link
                    all_deals.append({"title": title, "url": link, "source": name})
                except Exception:
                    continue
                    
        return all_deals