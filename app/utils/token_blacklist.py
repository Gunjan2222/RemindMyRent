import redis
from flask import current_app


class TokenBlacklist:
    """Manage JWT blacklist in Redis."""

    def __init__(self):
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def add(self, jti, expires_in):
        """Add JWT ID to Redis with expiration time."""
        self.redis.setex(f"blacklist:{jti}", expires_in, "true")

    def is_blacklisted(self, jti):
        """Check if the token is already blacklisted."""
        return self.redis.get(f"blacklist:{jti}") is not None
