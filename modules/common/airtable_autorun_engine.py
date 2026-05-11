# C:\SNS_24AutoProject_250723\modules\common\airtable_autorun_engine.py

import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
    raise ValueError("AIRTABLE_API_KEY / AIRTABLE_BASE_ID 환경변수 설정 필요")


BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

SOURCE_TABLE = "Source_Feeds"
POST_TABLE = "Instagram_Posts"

POLL_SECONDS = 30


def now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def airtable_request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{BASE_URL}/{path}"
    response = requests.request(
        method=method,
        url=url,
        headers=HEADERS,
        params=params,
        json=json_data,
        timeout=30,
    )

    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = {"raw_text": response.text}

        raise RuntimeError(
            f"Airtable API failed | method={method} | path={path} | "
            f"status={response.status_code} | detail={detail}"
        )

    return response.json()


def airtable_get_records(table_name: str, formula: Optional[str] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if formula:
        params["filterByFormula"] = formula

    data = airtable_request("GET", table_name, params=params)
    return data.get("records", [])


def airtable_create_record(table_name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"fields": fields}
    return airtable_request("POST", table_name, json_data=payload)


def airtable_update_record(table_name: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"fields": fields}
    return airtable_request("PATCH", f"{table_name}/{record_id}", json_data=payload)


def generate_caption(raw_text: str) -> str:
    text = safe_text(raw_text)
    if not text:
        text = "No content"
    return f"[AUTO GENERATED]\n{text[:120]}\n#AI #Automation #SNS"


def build_post_fields(source_fields: Dict[str, Any], insta_post_code: str, caption: str) -> Dict[str, Any]:
    """
    현재 Airtable_100_Final_n8n_Optimized_26413_0354am.xlsx 기준 필드만 사용.
    문제 발생했던 visibility_check 는 의도적으로 제외.
    """
    source_feed_code = safe_text(source_fields.get("source_feed_code"))
    account_code_ref = safe_text(source_fields.get("account_code_ref"))

    fields: Dict[str, Any] = {
        "insta_post_code": insta_post_code,
        "source_feed_code_ref": source_feed_code,
        "account_code_ref": account_code_ref,
        "caption": caption,
        "post_status": "scheduled",
        "moderation_status": "approved",
        "scheduled_upload_at": now_str(),
        "last_error_msg": "",
    }

    # 빈 값은 전송하지 않도록 최종 정리
    cleaned_fields = {}
    for key, value in fields.items():
        if value is None:
            continue
        cleaned_fields[key] = value

    return cleaned_fields


def update_source_success(record_id: str, insta_post_code: str) -> None:
    airtable_update_record(
        SOURCE_TABLE,
        record_id,
        {
            "processing_status": "post_created",
            "insta_post_code_ref": insta_post_code,
            "last_error_msg": "",
        },
    )


def update_source_error(record_id: str, error_message: str) -> None:
    airtable_update_record(
        SOURCE_TABLE,
        record_id,
        {
            "last_error_msg": error_message[:100000],
        },
    )


def process_gpt_ready_sources() -> None:
    records = airtable_get_records(
        SOURCE_TABLE,
        formula="{processing_status}='gpt_ready'",
    )

    print(f"[INFO] gpt_ready records: {len(records)}")

    for record in records:
        record_id = record["id"]
        fields = record.get("fields", {})

        source_feed_code = safe_text(fields.get("source_feed_code"))
        raw_content = safe_text(fields.get("raw_content"))
        account_code_ref = safe_text(fields.get("account_code_ref"))

        if not source_feed_code:
            print(f"[SKIP] source_feed_code 없음 | record_id={record_id}")
            continue

        try:
            caption = generate_caption(raw_content)
            insta_post_code = f"IP-{uuid.uuid4().hex[:8].upper()}"

            post_fields = build_post_fields(fields, insta_post_code, caption)
            created = airtable_create_record(POST_TABLE, post_fields)

            update_source_success(record_id, insta_post_code)

            print(
                f"[SUCCESS] source_feed_code={source_feed_code} "
                f"| account_code_ref={account_code_ref} "
                f"| insta_post_code={insta_post_code} "
                f"| created_post_id={created.get('id')}"
            )

        except Exception as exc:
            error_message = str(exc)
            print(
                f"[ERROR] source_feed_code={source_feed_code} "
                f"| record_id={record_id} "
                f"| detail={error_message}"
            )

            try:
                update_source_error(record_id, error_message)
            except Exception as update_exc:
                print(
                    f"[ERROR] source error update failed "
                    f"| record_id={record_id} "
                    f"| detail={update_exc}"
                )


def main_loop() -> None:
    print("[START] Airtable AutoRun Engine")

    while True:
        try:
            process_gpt_ready_sources()
        except Exception as exc:
            print(f"[FATAL] {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main_loop()