"""
Cost Guard — Monthly budget per user, Redis-backed.

Strategy: INCRBYFLOAT atomic trong Redis.
  Key:   cost:<user_id>:<YYYY-MM>
  Value: float USD spent this month
  TTL:   35 ngày

Pricing GPT-4o-mini:
  Input:  $0.00015 / 1K tokens
  Output: $0.00060 / 1K tokens

Default: $10.0 / user / month (MONTHLY_BUDGET_USD)
"""
import logging
from datetime import datetime, timezone

import redis as redis_lib
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

INPUT_COST_PER_1K  = 0.00015   # USD per 1K input tokens
OUTPUT_COST_PER_1K = 0.00060   # USD per 1K output tokens

_redis_client: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


def _month_key(user_id: str) -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"cost:{user_id}:{month}"


def check_budget(user_id: str) -> None:
    """
    Kiểm tra monthly budget TRƯỚC KHI gọi LLM.

    Raises:
        HTTPException 402 — nếu budget exhausted.
    """
    try:
        r = _get_redis()
        key = _month_key(user_id)
        spent_raw = r.get(key)
        spent = float(spent_raw) if spent_raw else 0.0
        budget = settings.MONTHLY_BUDGET_USD

        if spent >= budget:
            logger.warning(
                '{"event":"budget_exceeded","user_id":"%s","spent":%.4f,"budget":%.2f}',
                user_id, spent, budget,
            )
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Monthly budget exhausted: ${spent:.4f} / ${budget:.2f}. "
                    "Try again next month."
                ),
            )
    except HTTPException:
        raise
    except Exception as e:
        # Redis xuống → fail open
        logger.error('{"event":"budget_check_error","error":"%s"}', str(e))


def record_cost(user_id: str, input_tokens: int, output_tokens: int) -> float:
    """Ghi nhận cost sau khi LLM call thành công. Returns: cost USD."""
    cost = (
        (input_tokens  / 1000) * INPUT_COST_PER_1K +
        (output_tokens / 1000) * OUTPUT_COST_PER_1K
    )
    try:
        r = _get_redis()
        key = _month_key(user_id)
        new_total = r.incrbyfloat(key, cost)
        r.expire(key, 35 * 24 * 3600)
        logger.info(
            '{"event":"cost_recorded","user_id":"%s","cost_usd":%.6f,"monthly_usd":%.4f}',
            user_id, cost, new_total,
        )
    except Exception as e:
        logger.error('{"event":"cost_record_error","error":"%s"}', str(e))
    return cost
