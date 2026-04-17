"""
Authentication — API Key verification.

Client gửi header: X-API-Key: <key>
Server trả 401 nếu key sai hoặc thiếu.
User ID được derive từ key bằng hash → stable + stateless.
"""
import hashlib
from fastapi import Header, HTTPException
from app.config import settings


def verify_api_key(x_api_key: str = Header(..., description="API key xác thực")) -> str:
    """
    Xác thực API key từ header X-API-Key.

    Returns:
        user_id (str) — stable ID được hash từ key.
    Raises:
        HTTPException 401 — nếu key không hợp lệ.
    """
    if not x_api_key or x_api_key != settings.AGENT_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Add header: X-API-Key: <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    # Hash key → user_id (không expose key gốc trong logs)
    user_id = "user_" + hashlib.sha256(x_api_key.encode()).hexdigest()[:12]
    return user_id
