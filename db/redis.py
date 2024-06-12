try:
    from redis import asyncio as aioredis
except ImportError:
    import aioredis
from contextlib import asynccontextmanager
import redis
from fastapi import FastAPI

from core.config import settings


@asynccontextmanager
async def register_redis(app: FastAPI):
    """
    把redis挂载到app对象上面
    :param app:
    :return:
    """
    app.state.redis = await aioredis.from_url(settings.getRedisURL())
    yield
    await app.state.redis.close()
    
    

def get_redis() -> redis.Redis:
    """
    get_redis 同步的redis

    :return redis.Redis
    """
    pool = redis.ConnectionPool.from_url(settings.getRedisURL())
    return redis.Redis(connection_pool=pool)


async def get_async_redis() -> aioredis:
    """
    get_async_redis 获取异步的Redis
    """
    return await aioredis.from_url(settings.getRedisURL())