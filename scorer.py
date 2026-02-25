import google.generativeai as genai
import os
import logging
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HotdealScorer:
    """LLM API를 활용하여 핫딜의 정성적/정량적 점수를 산출하는 클래스"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("GEMINI_API_KEY environment variable is missing.")
        else:
            genai.configure(api_key=self.api_key)
        
        # 비용 효율을 위해 gemini-1.5-flash 모델 적용
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def analyze_deal(self, title: str, final_price: int, avg_price: int, comments: str) -> Dict[str, Any]:
        """수집된 텍스트와 댓글을 분석하여 최종 점수 및 브리핑 텍스트를 반환합니다."""
        
        # 1. PriceScore (가격 메리트 점수) 산출
        if avg_price > 0 and final_price > 0:
            price_score = min(max(((avg_price - final_price) / avg_price) * 100 * 1.5, 0), 100)
        else:
            price_score = 0 # 과거 데이터 부족

        # 2. TrustScore (판매처 신뢰도 점수 - 기본값 80. 향후 판매처 판별 로직 추가 시 변동)
        trust_score = 80 

        # 3. AIScore 산출 및 텍스트 요약을 위한 프롬프트 구성 (Zero-Inference 규칙 적용)
        prompt = f"""
        당신은 핫딜 평가 시스템입니다. 아래 제공된 데이터만을 기반으로 분석하십시오. 외부 정보 창작은 엄격히 금지됩니다.
        
        [제공 데이터]
        - 상품명: {title}
        - 최종 결제가: {final_price}원
        - 역대 평균가: {avg_price}원 (0일 경우 '과거 데이터 축적 중'으로 명시)
        - 커뮤니티 댓글 요약: {comments}
        
        [요구사항]
        1. 커뮤니티 댓글의 여론을 분석하여 0~100점 사이의 정수(ai_score)로 산출하십시오.
        2. 최종가 기준 평가 및 커뮤니티 반응을 2~3문장으로 요약한 텍스트(briefing)를 작성하십시오. 조건이 불명확하면 '{{조건 확인 필요}}'를 삽입하십시오.
        3. 반드시 아래의 JSON 형식으로만 응답하십시오.
        {{
            "ai_score": 정수,
            "briefing": "요약 텍스트"
        }}
        """

        try:
            # 비동기 LLM API 호출
            response = await self.model.generate_content_async(prompt)
            
            # JSON 텍스트 추출 (마크다운 포맷 백틱 제거)
            raw_text = response.text.replace('```json', '').replace('```', '').strip()
            result = json.loads(raw_text)
            
            ai_score = result.get('ai_score', 50)
            briefing = result.get('briefing', "분석 내용을 생성할 수 없습니다.")
            
            # 최종 점수 산출 (가중치 적용: 가격 40%, 신뢰도 30%, AI 30%)
            total_score = (price_score * 0.4) + (trust_score * 0.3) + (ai_score * 0.3)
            
            return {
                "price_score": round(price_score, 1),
                "trust_score": trust_score,
                "ai_score": ai_score,
                "total_score": round(total_score, 1),
                "briefing": briefing
            }
            
        except Exception as e:
            logger.error(f"LLM API Evaluation Error: {e}")
            return {
                "price_score": round(price_score, 1),
                "trust_score": trust_score,
                "ai_score": 0,
                "total_score": 0,
                "briefing": "API 통신 오류 또는 출력 포맷 에러로 인해 브리핑을 생성하지 못했습니다."
            }