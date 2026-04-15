import logging
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger("SAAITA")

# Single instances of extensions
limiter = Limiter(key_func=get_remote_address, default_limits=[])
redis_client = None
REDIS_AVAILABLE = False
redis_fallback = {}

def init_redis(redis_url):
    global redis_client, REDIS_AVAILABLE
    try:
        import redis
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("[OK] Redis connected via extensions")
        REDIS_AVAILABLE = True
    except Exception as e:
        is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
        if is_prod:
            raise SystemExit(f"[FATAL] Redis is required in production. Error: {e}")
            
        logger.warning(f"[WARN] Redis unavailable: {e}. Using in-memory fallback for development")
        redis_client = None
        REDIS_AVAILABLE = False

def init_limiter(app, redis_url):
    global limiter
    if REDIS_AVAILABLE:
        app.config["RATELIMIT_STORAGE_URI"] = redis_url
        limiter.init_app(app)
        logger.info("[OK] Rate limiter using Redis via extensions")
    else:
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"
        limiter.init_app(app)
        logger.warning("[WARN] Rate limiter using in-memory storage (development only) via extensions")
