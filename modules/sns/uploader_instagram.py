# modules/sns/uploader_instagram.py

"""
Instagram 업로드 모듈 (SNS 자동화)
- 이미지/동영상 업로드
- 캡션, 태그 처리
- 비동기 지원
"""

import asyncio
import os
from typing import Optional


VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".avi"}


def is_valid_file(file_path: str) -> bool:
    """
    파일 존재 여부 및 확장자 유효성 검사
    """
    _, ext = os.path.splitext(file_path)
    return os.path.isfile(file_path) and ext.lower() in VALID_EXTENSIONS


async def upload_post(file_path: str, caption: Optional[str] = None) -> bool:
    """
    Instagram에 게시물 업로드
    :param file_path: 업로드할 파일 경로
    :param caption: 게시물 캡션
    :return: 성공 여부 (True/False)
    """
    if not is_valid_file(file_path):
        print(f"[ERROR] 유효하지 않은 파일: {file_path}")
        return False

    try:
        print(f"[INFO] 업로드 시작: {file_path} (caption: {caption})")
        await asyncio.sleep(0.1)  # 실제 업로드 API 대체
        print(f"[INFO] 게시물 업로드 완료: {file_path}")
        return True
    except Exception as e:
        print(f"[ERROR] 게시물 업로드 실패: {e}")
        return False


async def upload_story(file_path: str) -> bool:
    """
    Instagram 스토리 업로드
    :param file_path: 업로드할 파일 경로
    :return: 성공 여부 (True/False)
    """
    if not is_valid_file(file_path):
        print(f"[ERROR] 유효하지 않은 파일: {file_path}")
        return False

    try:
        print(f"[INFO] 스토리 업로드 시작: {file_path}")
        await asyncio.sleep(0.1)  # 실제 업로드 API 대체
        print(f"[INFO] 스토리 업로드 완료: {file_path}")
        return True
    except Exception as e:
        print(f"[ERROR] 스토리 업로드 실패: {e}")
        return False
