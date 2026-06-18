from abc import ABC, abstractmethod

class ConnectorError(Exception):
    pass

class BaseCrawlConnector(ABC):

    @abstractmethod
    def fetch(self, target: dict) -> list:
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass
