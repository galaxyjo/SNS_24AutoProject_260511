# CURRENT_RUNTIME_CONTEXT.md
_마지막 업데이트: 260527 15:03_

## 현재 단계
Runtime Infra Recovery Complete
Business Flow Verification Pending

## Source of Truth
- Runtime: C:\SNS_24AutoProject_260511
- Archive: C:\SNS_24AutoProject_250723 (삭제/dead 판정 금지)

## 마지막 확인 커밋
1b2bfb2 (followup3 충돌 제거) — git commit 보류 중

## Runtime 상태 (260527 15:00 기준)
| 구간 | 상태 | 근거 |
|---|---|---|
| Flask (dm_receiver) | ✅ LIVE | /health 200 정상 |
| launcher/main.py | ✅ LIVE | scheduler_err.log 정상 |
| ngrok | ✅ LIVE | watchdog ok |
| Streamlit | ✅ LIVE | watchdog ok |
| FB Crawl | ✅ 실행됨 | _job_fb_crawl executed |
| Instagram Upload | ✅ 실행됨 | _job_insta_upload executed |
| DM 자동응답 | ⚠️ UNKNOWN | price inquiry DM 미수신 |
| Lead CRM | ⚠️ PARTIAL | bridge_status 옵션 미등록 |

## Known Fact
- DEFAULT_BASE_PRICE=50000 .env 설정 확인
- watchdog self-healing operational
- bridge_status=closed / lead_status=converted Airtable 미등록

## Unknown
- DEFAULT_BASE_PRICE 실제 runtime 반영 여부
- 실제 DM price inquiry 수신 시 자동응답 정상 여부
- Airtable price 필드 실제 값 (전체 빈값 확인됨)

## Next Investigation
1. 실제 DM 수신 후 AutoReply 로그 확인
2. Airtable bridge_status / lead_status 옵션 추가
3. git commit (E2E proof 확보 후)

## 절대 금지
- 250723 삭제/dead 판정
- 폴더 merge/전체 복사
- Evidence 없는 완료 선언
