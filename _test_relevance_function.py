import sys
sys.path.insert(0, r"C:\SNS_24AutoProject_260511")
from modules.crawlers.quality_gate import _is_irrelevant_category

titles = [
    "10X12+4cm OPP봉투 접착식 투명 비닐봉투 OPP 접착봉투",
    "이켈 포맨 프리미엄 콜라겐 기초세트(스킨2+로션1) 남성화장품 로션 스킨 선물세트",
    "2080 오리지날칫솔 5plus5 미세모",
    "가그린 오리지널 750ml 동아제약",
    "HZ680 틈새 화장대 400 2colors",
]
for t in titles:
    result = _is_irrelevant_category({"title": t})
    print(f"irrelevant={result} | {t}")
