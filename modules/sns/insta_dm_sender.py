# modules/sns/insta_dm_sender.py

import os
import time
import random
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def send_dm(user_id: str, message: str) -> bool:
    if not user_id or not message:
        logger.warning("Invalid DM parameters: user_id or message is empty.")
        return False

    try:
        logger.info(f"Sending DM to {user_id}: {message}")
        time.sleep(random.uniform(0.1, 0.3))  # Simulate network latency
        if "fail" in message.lower():
            raise ValueError("Simulated failure.")
        logger.info(f"DM sent to {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send DM to {user_id}: {e}")
        return False


def get_dm_message_template(index: int) -> str:
    templates = [
        "Hello! This is a test DM.",
        "Check out our new product launch!",
        "We appreciate your support. Thanks!",
        "fail-test",  # Intentionally failing template
    ]
    if 0 <= index < len(templates):
        return templates[index]
    return "Invalid template index."


def should_send_dm(user_data: dict) -> bool:
    return user_data.get("is_active", False) and not user_data.get("is_blocked", False)


def main_dm_dispatcher(user_list: list) -> int:
    sent_count = 0
    for user in user_list:
        if should_send_dm(user):
            msg = get_dm_message_template(user.get("template_index", 0))
            success = send_dm(user["user_id"], msg)
            if success:
                sent_count += 1
    return sent_count
