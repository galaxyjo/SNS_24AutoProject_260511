"""E2E 수동 실행 — FB크롤링 → 캡션 → Instagram 업로드"""
from dotenv import load_dotenv
load_dotenv(override=True)

from core.log_initializer import init_logging
init_logging()

print("=" * 60)
print("  E2E 수동 실행 — FB크롤링 → 캡션 → Instagram 업로드")
print("=" * 60)

# STEP 1: FB 크롤링
print("\n[STEP 1] FB 크롤링 시작...")
from modules.sns.facebook_crawler import run_all_accounts
summary = run_all_accounts(
    target_publish_account_code_ref="IDN-000041",
    data_classification="production",
)
print(f"[STEP 1] 완료 | {summary}")

# STEP 2: Instagram 업로드
print("\n[STEP 2] Instagram 업로드 시작...")
from launcher.main import _job_insta_upload
_job_insta_upload()

print("\n" + "=" * 60)
print("  E2E 완료")
print("=" * 60)
