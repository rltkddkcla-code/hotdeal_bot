import aiosqlite
import os
import logging
from typing import Optional, List, Dict, Any

# 로깅 설정
logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite 데이터베이스 관리를 위한 비동기 클래스"""
    
    def __init__(self, db_path: str = "data/hotdeals.db"):
        self.db_path = db_path
        self._ensure_dir()

    def _ensure_dir(self):
        """데이터베이스 파일 저장을 위한 디렉토리 확인 및 생성"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_db(self):
        """테이블 스키마 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS hotdeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    final_price INTEGER NOT NULL,
                    total_score REAL NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('NEW', 'UPLOADED', 'PENDING', 'DISCARDED')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
            logger.info("Database schema initialized successfully.")

    async def is_url_exists(self, url: str) -> bool:
        """URL 중복 검증 (수집 단계에서 호출)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT 1 FROM hotdeals WHERE url = ?', (url,)) as cursor:
                result = await cursor.fetchone()
                return result is not None

    async def insert_deal(self, url: str, title: str, final_price: int, total_score: float, status: str = 'NEW') -> Optional[int]:
        """분석이 완료된 신규 핫딜 데이터 삽입"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO hotdeals (url, title, final_price, total_score, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (url, title, final_price, total_score, status))
                await db.commit()
                return cursor.lastrowid
        except aiosqlite.IntegrityError:
            # UNIQUE 제약 조건(url) 위반 시 중복으로 간주
            logger.warning(f"Duplicate deal insertion blocked: {url}")
            return None

    async def update_status(self, deal_id: int, new_status: str) -> bool:
        """텔레그램 인라인 버튼 입력을 통한 상태값 업데이트"""
        valid_statuses = ('NEW', 'UPLOADED', 'PENDING', 'DISCARDED')
        if new_status not in valid_statuses:
            logger.error(f"Invalid status value: {new_status}")
            return False

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                UPDATE hotdeals 
                SET status = ? 
                WHERE id = ?
            ''', (new_status, deal_id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_pending_deals(self) -> List[Dict[str, Any]]:
        """명령어 /pending 호출 시 보류 상태인 핫딜 목록 반환"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT id, url, title, final_price, total_score, created_at 
                FROM hotdeals 
                WHERE status = "PENDING" 
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]