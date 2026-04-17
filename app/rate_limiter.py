"""
Rate Limiter — Sliding Window, Redis-backed.

Strategy: Sorted Set trong Redis lưu timestamps của từng request.
  Key:   ratelimit:<user_id>
  Score: Unix timestamp
  TTL:   60 giây

Tại mỗi request:
  1. ZREMRANGEBYSCORE — xoá timestamps cũ hơn 60s
  2. ZCARD           — đếm requests trong window
  3. Nếu >= limit    → HTTP 429
  4. Ngược lại       → ZADD timestamp mới

Tất cả bước trên chạy trong Redis pipeline → atomic + hiệu quả.
"""
import time
import logging

import redis as redis_lib
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

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


def check_rate_limit(user_id: str) -> None:
    """
    Kiểm tra sliding window rate limit cho user.

    Raises:
        HTTPException 429 — nếu vượt quá giới hạn.
    """
    try:
        r = _get_redis()
        now = time.time()
        window_start = now - 60
        key = f"ratelimit:{user_id}"
        limit = settings.RATE_LIMIT_PER_MINUTE

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)  # xoá cũ
        pipe.zcard(key)                                    # đếm hiện tại
        pipe.zadd(key, {str(now): now})                    # thêm request này
        pipe.expire(key, 60)                               # auto-cleanup
        results = pipe.execute()

        current_count = results[1]  # count TRƯỚC KHI add request mới

        if current_count >= limit:
            logger.warning(
                '{"event":"rate_limited","user_id":"%s","count":%d,"limit":%d}',
                user_id, current_count, limit,
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min. Retry after 60s.",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        remaining = limit - current_count - 1
        logger.debug(
            '{"event":"rate_check_ok","user_id":"%s","remaining":%d}',
            user_id, remaining,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Redis xuống → fail open (cho qua, log lỗi)
        logger.error('{"event":"rate_limit_redis_error","error":"%s"}', str(e))
