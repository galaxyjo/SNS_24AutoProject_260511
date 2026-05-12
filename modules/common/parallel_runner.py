"""
parallel_runner.py — 다계정 병렬 태스크 실행기

사용법:
    from modules.common.parallel_runner import run_parallel

    def crawl_task(account):
        from modules.sns.facebook_crawler import run_all_accounts
        # 계정별 작업 수행
        ...

    results = run_parallel(crawl_task, max_workers=3)
    # [{"account": "account1", "status": "ok", "result": ...}, ...]
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any

from modules.common.account_manager import get_active_accounts, Account
from modules.common.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_WORKERS = int(os.getenv("PARALLEL_MAX_WORKERS", "3"))


def run_parallel(
    task_fn: Callable[[Account], Any],
    accounts: list[Account] | None = None,
    max_workers: int = _DEFAULT_WORKERS,
    timeout: float | None = None,
) -> list[dict]:
    """활성 계정 전체에 task_fn을 병렬 실행하고 결과를 반환한다.

    Args:
        task_fn:     Account를 인자로 받는 함수. 예외 발생 시 해당 계정만 실패 처리.
        accounts:    None이면 get_active_accounts() 사용.
        max_workers: 동시 실행 스레드 수 (기본 3, env PARALLEL_MAX_WORKERS).
        timeout:     태스크당 최대 대기 시간(초). None이면 무제한.

    Returns:
        [{"account": name, "status": "ok"|"error", "result": ..., "error": ...}, ...]
    """
    targets = accounts if accounts is not None else get_active_accounts()
    if not targets:
        logger.warning("[ParallelRunner] 실행 가능한 계정 없음")
        return []

    workers = min(max_workers, len(targets))
    logger.info(f"[ParallelRunner] 시작 | accounts={len(targets)} | workers={workers}")

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_acct = {pool.submit(task_fn, acct): acct for acct in targets}
        for future in as_completed(future_to_acct, timeout=timeout):
            acct = future_to_acct[future]
            try:
                result = future.result()
                results.append({"account": acct.name, "status": "ok", "result": result})
                logger.info(f"[ParallelRunner] 완료 | account={acct.name}")
            except Exception as exc:
                results.append({"account": acct.name, "status": "error", "error": str(exc)})
                logger.error(f"[ParallelRunner] 실패 | account={acct.name} | {exc}")

    ok  = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] == "error")
    logger.info(f"[ParallelRunner] 완료 | ok={ok} error={err}")
    return results
