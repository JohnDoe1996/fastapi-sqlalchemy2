from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apps import api_router
from starlette.middleware.cors import CORSMiddleware
from common.middleware import RequestsLoggerMiddleware

from common.exceptions import customExceptions
from core.config import settings
from db.redis import register_redis
from db.session import async_session_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with register_redis(app):
        yield
    if async_session_manager.engine is not None:
        # Close the DB connection
        await async_session_manager.close()


def create_app():
    app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
    # set middleware
    # register_middleware(app)
    app.middleware("http")(RequestsLoggerMiddleware())  # http请求请求记录中间件  不需要可以注释掉，使用了可能会影响一点请求速度
    # api router
    app.include_router(api_router, prefix="/api/v1")
    # set socketio
    # app.mount('/', socket_app)
    # set static files
    app.mount("/media", StaticFiles(directory="media"), name="media")   # 媒体文件
    # allow cross domain
    app.add_middleware(CORSMiddleware, allow_origins=settings.BACKEND_CORS_ORIGINS,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    # set custom exceptions
    customExceptions(app)
    # # print all path
    # for _route in app.routes:
    #     r = _route.__dict__
    #     print(f"{','.join(tuple(r.get('methods', {}))):<10}{r['path']}")
    return app



app = create_app()


if __name__ == '__main__':
    import uvicorn
    # Don't set debug/reload equals True in release, because TimedRotatingFileHandler can't support multi-prcoess
    # please used "uvicorn --host 127.0.0.1 --port 8000 main:app --env-file ./configs/.env" run in release, and used "python main.py" in dev
    uvicorn.run(
        app='main:app',
        host=str(settings.HOST),
        port=settings.PORT,
        reload=settings.RELOAD,
        log_config=str(settings.LOGGING_CONFIG_FILE)
    )
    
    
"""
Celery schedule worker

1) start worker in project base path
    
    celery -A workers  worker -l info -c 1
    
2) start beat in project base path

    celery -A workers beat -l info
    
"""