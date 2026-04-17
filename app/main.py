"""
Production AI Agent - Main Application

Ket hop tat ca concepts:
  [OK] Config tu environment (12-factor)
  [OK] Structured JSON logging
  [OK] API Key authentication
  [OK] Rate limiting (10 req/min per user, Redis sliding window)
  [OK] Cost guard ($10/month per user, Redis)
  [OK] Conversation history (Redis, stateless design)
  [OK] Input validation (Pydantic)
  [OK] Health check endpoint
  [OK] Readiness probe endpoint
  [OK] Graceful shutdown (SIGTERM)
  [OK] Security headers
  [OK] CORS
  [OK] Streaming responses
"""
import time
import signal
import logging
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis as redis_lib
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost

# -------------------------------------------------------------
# Structured JSON Logging
# -------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":%(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Globals
# -------------------------------------------------------------
START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# -------------------------------------------------------------
# Redis helper
# -------------------------------------------------------------
_redis_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


# -------------------------------------------------------------
# Conversation History (Redis-backed - stateless design)
# -------------------------------------------------------------
def get_history(conversation_id: str) -> list[dict]:
    """Lay lich su hoi thoai tu Redis."""
    try:
        r = get_redis()
        key = f"history:{conversation_id}"
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.error('"get_history_error: %s"', str(e))
    return []


def save_history(conversation_id: str, messages: list[dict]) -> None:
    """Luu lich su hoi thoai vao Redis voi TTL."""
    try:
        r = get_redis()
        key = f"history:{conversation_id}"
        trimmed = messages[-settings.MAX_HISTORY_MESSAGES:]
        r.setex(key, settings.HISTORY_TTL_SECONDS, json.dumps(trimmed))
    except Exception as e:
        logger.error('"save_history_error: %s"', str(e))


# -------------------------------------------------------------
# LLM Caller - OpenAI hoac Mock
# -------------------------------------------------------------
def call_llm(messages: list[dict]) -> tuple[str, int, int]:
    """
    Goi LLM voi conversation history.

    Returns:
        (answer, input_tokens, output_tokens)
    """
    if settings.OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
            )
            answer = resp.choices[0].message.content.strip()
            input_tokens = resp.usage.prompt_tokens
            output_tokens = resp.usage.completion_tokens
            return answer, input_tokens, output_tokens
        except Exception as e:
            logger.error('"openai_error: %s"', str(e))
    # Mock LLM
    import random, time as _t
    _t.sleep(0.1)
    user_msg = messages[-1]["content"].lower() if messages else ""
    mock_answers = {
        "docker": "Docker la cong cu containerization giup dong goi app va dependencies. Build once, run anywhere!",
        "redis": "Redis la in-memory data store, dung cho caching, session, pub/sub, rate limiting. Rat nhanh!",
        "deploy": "Deployment la dua code len server de nguoi dung access duoc. Co the dung Railway, Render, hoac VPS.",
        "nginx": "Nginx la web server / reverse proxy / load balancer. O day dung de phan phoi load giua 3 agent instances.",
        "api": "REST API cho phep clients gui HTTP requests de tuong tac voi backend. Dung JSON de truyen data.",
    }
    for keyword, answer in mock_answers.items():
        if keyword in user_msg:
            word_count = len(answer.split())
            return answer, len(user_msg.split()) * 2, word_count * 2

    answers = [
        "Toi la Production AI Agent dang chay trong Docker container! Hoi toi ve Docker, Redis, hay deployment nhe.",
        "Agent dang hoat dong tot voi rate limiting, cost guard, va Redis-backed conversation history.",
        "Moi cau tra loi cua toi duoc load-balanced qua Nginx toi mot trong 3 agent instances!",
    ]
    answer = random.choice(answers)
    return answer, 50, len(answer.split()) * 2


async def stream_llm(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Streaming response - yield tung chunk."""
    answer, _, _ = call_llm(messages)
    words = answer.split()
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f"data: {json.dumps({'delta': chunk})}\n\n"
        import asyncio
        await asyncio.sleep(0.05)
    yield "data: [DONE]\n\n"


# -------------------------------------------------------------
# Graceful Shutdown (SIGTERM)
# -------------------------------------------------------------
def _handle_sigterm(signum, _frame):
    global _is_ready
    _is_ready = False
    logger.info('"SIGTERM received - graceful shutdown initiated"')


signal.signal(signal.SIGTERM, _handle_sigterm)


# -------------------------------------------------------------
# Lifespan
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(
        '"startup","app":"%s","version":"%s","env":"%s"',
        settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT,
    )
    try:
        get_redis().ping()
        logger.info('"redis_connected"')
    except Exception as e:
        logger.warning('"redis_not_available: %s"', str(e))
    _is_ready = True
    logger.info('"ready"')
    yield
    _is_ready = False
    logger.info('"shutdown"')


# -------------------------------------------------------------
# FastAPI App
# -------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration_ms = round((time.time() - start) * 1000, 1)
        logger.info(
            '"request","method":"%s","path":"%s","status":%d,"ms":%.1f',
            request.method, request.url.path, response.status_code, duration_ms,
        )
        return response
    except Exception:
        _error_count += 1
        raise


# -------------------------------------------------------------
# Pydantic Models
# -------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Cau hoi cho agent")
    conversation_id: str | None = Field(None, description="ID de duy tri conversation history")
    stream: bool = Field(False, description="Bat streaming response")


class AskResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str
    model: str
    cost_usd: float
    timestamp: str


# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------
@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "ask":    "POST /ask  (requires X-API-Key)",
            "health": "GET  /health",
            "ready":  "GET  /ready",
            "docs":   "GET  /docs",
        },
    }


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "llm": "openai" if settings.OPENAI_API_KEY else "mock",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        get_redis().ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"
    return {"ready": True, "redis": redis_status}


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask(
    body: AskRequest,
    user_id: str = Depends(verify_api_key),
):
    check_rate_limit(user_id)
    check_budget(user_id)
    conv_id = body.conversation_id or str(uuid.uuid4())
    history = get_history(conv_id)

    messages = [
        {"role": "system", "content": (
            "Ban la mot AI agent huu ich, chuyen ve cloud deployment va DevOps. "
            "Tra loi ngan gon, chinh xac."
        )}
    ] + history + [
        {"role": "user", "content": body.question}
    ]

    logger.info(
        '"agent_call","user_id":"%s","conv_id":"%s","q_len":%d,"history_len":%d',
        user_id, conv_id, len(body.question), len(history),
    )

    if body.stream:
        async def event_stream():
            async for chunk in stream_llm(messages):
                yield chunk
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    answer, input_tokens, output_tokens = call_llm(messages)

    history.append({"role": "user", "content": body.question})
    history.append({"role": "assistant", "content": answer})
    save_history(conv_id, history)

    cost = record_cost(user_id, input_tokens, output_tokens)

    return AskResponse(
        conversation_id=conv_id,
        question=body.question,
        answer=answer,
        model=settings.LLM_MODEL,
        cost_usd=round(cost, 6),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    logger.info('"starting %s on %s:%d"', settings.APP_NAME, settings.HOST, settings.PORT)
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        timeout_graceful_shutdown=30,
        access_log=False,
    )
