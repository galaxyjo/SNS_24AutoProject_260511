"""
modules/infra/repository_interface.py
데이터 저장소 추상 인터페이스. 구현체는 저장소 종류와 무관하게 이 계약을 따른다.
"""
from abc import ABC, abstractmethod


class RepositoryInterface(ABC):

    @abstractmethod
    def fetch_one(
        self,
        table_name: str,
        filters: dict | None = None,
    ) -> dict | None:
        """조건에 맞는 레코드 1건 반환. 없으면 None."""

    @abstractmethod
    def fetch_all(
        self,
        table_name: str,
        filters: dict | None = None,
        fields: list[str] | None = None,
    ) -> list[dict]:
        """조건에 맞는 레코드 전체 반환."""

    @abstractmethod
    def update(
        self,
        table_name: str,
        record_id: str,
        data: dict,
    ) -> dict:
        """record_id 레코드를 data로 부분 업데이트. 업데이트된 레코드 반환."""

    @abstractmethod
    def insert(
        self,
        table_name: str,
        data: dict,
    ) -> dict:
        """새 레코드 생성. 생성된 레코드 반환."""

    @abstractmethod
    def delete(
        self,
        table_name: str,
        record_id: str,
    ) -> bool:
        """record_id 레코드 삭제. 성공 여부 반환."""
