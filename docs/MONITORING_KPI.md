# MONITORING_KPI.md — KPI / 모니터링 기준서

> 기준일: 2026-05-14 | 버전: v1.0

---

## KPI 지표 정의

| 지표 | 측정 단위 | 수집 주기 | 목표값 |
|------|-----------|-----------|--------|
| 일일 Upload 수 | 건/일 | 1시간 | ≥ 5건 |
| Upload 성공률 | % | 1시간 | ≥ 95% |
| DM 수신 수 | 건/일 | 실시간 | — |
| Lead 전환율 | % | 1시간 | ≥ 30% |
| 팔로업 성공률 | % | 1시간 | ≥ 70% |
| 댓글 자동 답글 수 | 건/일 | 15분 | — |
| retry_queue 적체 | 건 | 1시간 | ≤ 10건 |
| 주문 전환율 | % | 일간 | ≥ 10% |

---

## KPI 수집 구조

```python
from modules.metrics.kpi_collector import collect_kpi, run_hourly_snapshot

# 기간별 조회
kpi = collect_kpi('today')   # 오늘
kpi = collect_kpi('7d')      # 최근 7일
kpi = collect_kpi('30d')     # 최근 30일

# 반환 구조
{
    'upload':   {'total': int, 'success': int, 'fail': int, 'rate': float},
    'lead':     {'total': int, 'converted': int, 'rate': float},
    'followup': {'sent': int, 'success': int, 'rate': float},
    'comment':  {'polled': int, 'replied': int},
    'queue':    {'pending': int, 'failed': int}
}
```

---

## 모니터링 도구

### 대시보드
```powershell
python dashboard.py
# http://localhost:8501
# 탭: KPI / 업로드 현황 / Lead 현황 / 댓글 현황
```

### 헬스 모니터
```powershell
python -m modules.common.health_monitor
# 출력: services 상태 / retry_queue 통계 / 최근 에러
```

### Slack 알림 채널
- 기동/종료 이벤트
- 에러 발생 (P1/P2)
- 일간 KPI 리포트 (09:00)
- watchdog 재시작 이벤트

---

## KPI 등급 기준

| 등급 | 조건 |
|------|------|
| A (우수) | Upload 성공률 ≥ 95%, Lead 전환율 ≥ 30% |
| B (양호) | Upload 성공률 ≥ 85%, Lead 전환율 ≥ 20% |
| C (주의) | Upload 성공률 ≥ 70% 또는 Lead 전환율 ≥ 10% |
| D (위험) | 그 외 — 즉시 점검 필요 |

---

## SQLite 스냅샷

```
db/kpi_snapshots.db
  └── snapshots 테이블
        ├── timestamp
        ├── period
        └── kpi_json (JSON 직렬화)
```

조회:
```python
import sqlite3, json
conn = sqlite3.connect('db/kpi_snapshots.db')
rows = conn.execute("SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT 24").fetchall()
```
