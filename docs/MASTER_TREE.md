# MASTER_TREE.md — 전체 파일 구조 기준서

> 기준일: 2026-05-14 | 버전: v1.0

---

## 저장소 구조

```
C:\SNS_24AutoProject_260511\
├── launcher\                        ▶ 전체 실행 진입점
│   ├── main.py                      ✅ BackgroundScheduler + Flask + retry_queue
│   └── scheduler\
├── core\                            ▶ 실행 컨트롤러 / 태스크 라우터
│   ├── log_initializer.py           ✅ 시작 시 중앙 로거 1회 초기화
│   ├── error_handler.py             ✅ @handle_errors 데코레이터 / safe_run()
│   ├── task_router.py               ✅ 태스크 이름 → 핸들러 분기
│   └── run_engine.py                ✅ APScheduler 오케스트레이터
├── modules\
│   ├── sns\          [F-01~F-04]    ▶ FB 크롤링 / Instagram 업로드
│   │   ├── facebook_crawler.py      ✅ Selenium + AdsPower Attach
│   │   ├── instagram_uploader.py    ✅ Graph API 업로드 (재시도 3회)
│   │   ├── caption_generator.py     ✅ Gemini 캡션 생성
│   │   └── pipeline_feed_ingest.py  ✅ Airtable Source_Feeds 파이프라인
│   ├── dm\           [F-05~F-06]    ▶ DM 수신 / 자동응답 / 팔로업
│   │   ├── dm_receiver.py           ✅ Meta Webhook DM 수신
│   │   ├── dm_auto_reply.py         ✅ Gemini 자동응답 (템플릿 폴백)
│   │   └── dm_followup_scheduler.py ✅ 팔로업 DM 스케줄러
│   ├── comment\                     ▶ 자동 댓글 관리
│   │   ├── comment_poller.py        ✅ Graph API 댓글 수집
│   │   └── comment_auto_reply.py    ✅ 자동 댓글 답글
│   ├── crm\                         ▶ Lead CRM
│   │   ├── lead_scorer.py           ✅ 리드 점수 산정
│   │   ├── order_detector.py        ✅ 주문 의도 감지
│   │   └── daily_report.py          ✅ 일간 리포트
│   ├── common\                      ▶ 공통 유틸
│   │   ├── airtable_bridge.py       ✅ Airtable CRUD 추상화
│   │   ├── logger.py                ✅ 중앙 로거
│   │   ├── retry_queue.py           ✅ 실패 태스크 재시도 (SQLite)
│   │   ├── health_monitor.py        ✅ 서비스 상태 체크
│   │   ├── account_manager.py       ✅ 다계정 관리
│   │   └── parallel_runner.py       ✅ ThreadPoolExecutor 병렬 실행
│   ├── metrics\      [F-10]         ▶ KPI 수집기
│   │   └── kpi_collector.py         ✅ SQLite 스냅샷 + 대시보드 연동
│   ├── interaction_engine\ [F-11]   ▶ 좋아요·댓글·공유 자동화
│   │   ├── engagement_tracker.py    ✅ like_count / comments_count 갱신
│   │   ├── auto_liker.py            ✅ 댓글 자동 좋아요
│   │   └── interaction_scheduler.py ✅ 15분 간격 스케줄
│   ├── trade\        [F-07]         ⏸ 보류 (Phase 3)
│   └── avatar\       [F-08]         ⏸ 보류 (Phase 3)
├── services\
│   └── slack_notifier.py            ✅ Incoming Webhook 알림
├── configs\
│   └── accounts.json                ✅ 다계정 설정 (없으면 .env 폴백)
├── db\
│   ├── retry_queue.db               실패 태스크 영속 저장
│   ├── kpi_snapshots.db             시간별 KPI 스냅샷
│   └── liked_comments.db            중복 좋아요 방지
├── docs\                            ← 현재 위치
├── logs\
│   ├── summary\app.log
│   ├── error\error.log
│   └── function\{모듈명}.log
├── tools\integrity\
├── tests\
├── backup\
├── dashboard.py
├── run_scheduler.ps1
└── watchdog.ps1
```

---

## 데이터 흐름

```
Facebook → [facebook_crawler] → Airtable(Source_Feeds)
         → [instagram_uploader] → Instagram Post
         → [engagement_tracker] → Airtable(ig_media_id / like_count)

Instagram DM → Meta Webhook → [dm_receiver] → Airtable(Lead_Interactions)
             → [dm_auto_reply] → Gemini → DM 발송
             → [dm_followup_scheduler] → 팔로업 DM

Lead_Interactions → [lead_scorer] → 점수 산정
                 → [order_detector] → 주문 의도 감지
                 → [daily_report] → Slack 알림
```
