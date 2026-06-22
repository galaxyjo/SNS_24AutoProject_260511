import os
import requests
from pyairtable import Api
from modules.infra.airtable_usage_logger import log_api_call

# ENV LOCK
API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

# pyairtable API 객체 (추가)
_api = Api(API_KEY)

# 🔒 Function Signature Lock (절대 변경 금지)
def get_table(table_name: str):
    return _api.table(BASE_ID, table_name)

# Airtable GET (ready 1건 조회)
def fetch_ready_one(table_name: str):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_name}"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    params = {
        "filterByFormula": "{post_status}='ready'",
        "maxRecords": 1
    }

    res = requests.get(url, headers=headers, params=params)
    log_api_call(table_name, "GET")
    return res.json().get("records", [])

# Airtable UPDATE (status 변경)
def update_record(table_name: str, record_id: str, data: dict):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_name}/{record_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "fields": data
    }

    requests.patch(url, headers=headers, json=payload)
    log_api_call(table_name, "PATCH")