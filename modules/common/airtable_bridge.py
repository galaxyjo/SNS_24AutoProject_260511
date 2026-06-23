import os
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
