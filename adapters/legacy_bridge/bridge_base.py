"""
LegacyBridge base contract for 250723 → 260511 migration.
All bridge modules must inherit this class and satisfy the contract
before any execute() call is permitted.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from modules.common.logger import get_logger

logger = get_logger("legacy_bridge")


@dataclass
class BridgeContext:
    module_name: str
    source_path: str
    target_runtime: str
    import_source: str = ""
    db_write_target: str = ""
    executed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class LegacyBridge(ABC):
    """
    Base contract for all legacy bridge adapters.

    Rules (BRIDGE_SKELETON_POLICY §4):
      - validate() must pass before execute() is called
      - rollback() must be called on execute() failure
      - all path / import / DB targets must be logged
    """

    def __init__(self, context: BridgeContext):
        self.ctx = context
        self._validated = False

    # ------------------------------------------------------------------ #
    # Contract interface                                                   #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def validate(self) -> bool:
        """Verify import path, DB target, runtime PID, config/env source.
        Must set self._validated = True on success."""

    @abstractmethod
    def execute(self) -> bool:
        """Run the migration step. Only callable after validate() passes."""

    @abstractmethod
    def rollback(self) -> bool:
        """Restore previous state. Must be idempotent."""

    # ------------------------------------------------------------------ #
    # Orchestration helpers                                                #
    # ------------------------------------------------------------------ #

    def run(self) -> bool:
        """Contract-first execution: validate → execute → rollback on failure."""
        self._log_context()

        if not self.validate():
            logger.error("[%s] validate() failed — execute() blocked", self.ctx.module_name)
            return False

        self._validated = True
        logger.info("[%s] validate() PASS — proceeding to execute()", self.ctx.module_name)

        try:
            result = self.execute()
            if result:
                logger.info("[%s] execute() SUCCESS", self.ctx.module_name)
            else:
                logger.error("[%s] execute() returned False — initiating rollback()", self.ctx.module_name)
                self.rollback()
            return result
        except Exception as exc:
            logger.error("[%s] execute() raised %s — initiating rollback()", self.ctx.module_name, exc)
            self.rollback()
            return False

    def _log_context(self):
        logger.info(
            "[%s] BridgeContext | source=%s | target=%s | import=%s | db=%s",
            self.ctx.module_name,
            self.ctx.source_path,
            self.ctx.target_runtime,
            self.ctx.import_source,
            self.ctx.db_write_target,
        )
