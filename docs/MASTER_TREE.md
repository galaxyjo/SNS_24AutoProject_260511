=&gt;251015_1515pm 
interaction_engine 폴더는 "계정 간 상호작용 자동화(좋아요·댓글·공유)" 전용 핵심 모듈
=&gt;13_final_master_tree_0929_1112am.txt 구조에
신규 모듈 modules/interaction_engine/ 폴더를 추가한 정식 병합 버전입니다.
(MasterTree 호환 + 태그·각주 포함)

✅ 업데이트된 MasterTree (251015 수정판)
✅ 업데이트된 MasterTree (251015 수정판)
C:\SNS_24AutoProject_250723\
├── launcher\
│   ├── main.py                             ▶ 전체 실행 진입점
│   └── scheduler\                          ▶ 스케줄러 전용 폴더
│       └── __init__.py

├── core\
│   ├── run_engine.py                       ▶ 실행 컨트롤러
│   ├── task_router.py                      ▶ 실행 분기 처리기
│   ├── log_initializer.py
│   ├── error_handler.py
│   └── __init__.py

├── modules\                                ✅ 기능 모듈
│   ├── sns\                                ▶ F-01~F-04 (크롤링·업로드)
│   │   ├── facebook_crawler.py
│   │   ├── insta_uploader.py
│   │   ├── insta_scheduler.py
│   │   ├── insta_upload_core.py
│   │   ├── text_cleaner.py
│   │   ├── image_generator.py
│   │   ├── hashtag_builder.py
│   │   └── __init__.py
│
│   ├── dm\                                 ▶ F-05~F-06 (DM·댓글·좋아요)
│   │   ├── bot.py
│   │   ├── bot_direct.py
│   │   ├── bot_comment.py
│   │   ├── bot_like.py
│   │   ├── insta_dm_sender.py
│   │   ├── insta_login.py
│   │   ├── api_utils.py
│   │   ├── friend_adder.py
│   │   ├── dm_scheduler.py
│   │   └── __init__.py
│
│   ├── trade\                              ▶ F-07 (거래/상품)
│   │   ├── quote_engine.py
│   │   ├── product_db_manager.py
│   │   ├── reply_generator.py
│   │   └── __init__.py
│
│   ├── avatar\                             ▶ F-08 (아바타·AI 반응)
│   │   ├── avatar_dispatcher.py
│   │   ├── decision_engine.py
│   │   ├── preset_reactor.py
│   │   └── __init__.py
│
│   ├── metrics\                            ▶ F-10 (통계 수집)
│   │   └── collector.py
│
│   ├── common\                             ▶ 공통 유틸·DB·로거
│   │   ├── logger.py
│   │   ├── db.py
│   │   ├── utils.py
│   │   ├── contact_replacer.py
│   │   ├── session_handler.py
│   │   ├── recovery_manager.py
│   │   ├── safe_ssl.py
│   │   ├── safe_os.py
│   │   ├── queue_util.py
│   │   ├── my_configparser.py
│   │   ├── pretty_output.py
│   │   ├── dt_util.py
│   │   ├── asyncio_custom.py
│   │   ├── proj_concurrent.py
│   │   ├── json_helper.py
│   │   ├── socket_handler.py
│   │   └── __init__.py
│
│   ├── interaction_engine\                 ⏺ **신규 F-11 상호작용 자동화 모듈**
│   │   ├── __init__.py                     ▶ 패키지 초기화
│   │   ├── scheduler.py                    ▶ 상호작용 주기 제어 (async 트리거)
│   │   ├── executor.py                     ▶ 좋아요·댓글·공유 실행 엔진
│   │   ├── logger.py                       ▶ 로그/DB 기록 및 SHA256 무결성
│   │   ├── config_loader.py                ▶ 계정·환경설정 로더(JSON·ENV)
│   │   └── __main__.py                     ▶ 독립 실행 진입점 (테스트용)
│
│   └── __init__.py                         ▶ 상위 모듈 초기화
│
├── services\
│   ├── gpt_connector.py
│   ├── smtp_mailer.py
│   ├── slack_notifier.py
│   ├── translator.py
│   ├── license_manager.py                  ⏺ 판매/라이선스 관리(확장용)
│   └── __init__.py
│
├── configs\
│   ├── env.json
│   ├── avatar_config.yaml
│   ├── trade_rules.yaml
│   ├── dm_config.yaml
│   ├── scheduler_config.json
│   └── interaction_config.json             ⏺ 상호작용 모듈 설정
│
├── data\
│   ├── fb_posts.json
│   ├── price_requests.json
│   ├── interaction_log.csv
│   └── exported_data\
│       └── *.xlsx
│
├── logs\
│   ├── summary\
│   ├── error\
│   ├── function\
│   ├── response_log.txt
│   ├── interaction_log.json                ⏺ 상호작용 결과 로그
│   └── obsolete_0520\
│
├── db\
│   ├── interaction_log.db                  ⏺ 상호작용 기록 DB
│
├── tools\
│   └── integrity\
│       ├── sha256_integrity_mastertree.py
│       ├── verify_integrity_and_identify_unnecessary.py
│       └── generate_interaction_hash.py    ⏺ 로그 무결성 자동검증 (신규)
│
├── tests\
│   ├── test_insta_dm.py
│   ├── test_fb_crawler.py
│   ├── test_avatar.py
│   ├── test_trade.py
│   ├── test_utils.py
│   ├── test_metrics.py
│   └── test_interaction_engine.py          ⏺ 신규 모듈 전용 테스트
│
└── backup\
    ├── SNS_24AutoProject_FINAL_20250518.zip
    ├── SNS_24AutoProject_BACKUP_20250509_012121.zip
    └── RECOVERED_20250519\



📘 주석 요약

modules/interaction_engine/ → 신규 핵심 모듈 (F-11)

scheduler.py: 계정 리스트 기반 자동 주기 트리거

executor.py: 실제 상호작용(좋아요·댓글·공유) 실행

logger.py: JSON + DB 로그 기록, SHA256 무결성 체크

config_loader.py: 계정/환경 설정 JSON 로드

main.py: 단독 실행 및 DRY-RUN 테스트 진입점

연관 항목:

configs/interaction_config.json (모듈 환경파일)

db/interaction_log.db (로그DB)

logs/interaction_log.json (액션 기록)

tests/test_interaction_engine.py (단위검증)
