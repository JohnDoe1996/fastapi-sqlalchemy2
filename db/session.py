import contextlib
import warnings
from typing import Any, Generator, AsyncGenerator 
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings

class SessionManager:
    def __init__(self, host: str, **engine_kwargs):
        self.engine = create_engine(host, **engine_kwargs)
        self.session_local = sessionmaker(autocommit=False, bind=self.engine)

    def close(self):
        if self.engine is None:
            warnings.warn("Manager is not initialized", DeprecationWarning)
            return
        self.engine.dispose()
        self.engine = None
        self.session_local = None

    @contextlib.contextmanager
    def connect(self) -> Generator[Session, None, None]:
        if self.engine is None:
            raise Exception("Manager is not initialized")
        with self.engine.begin() as connection:
            try:
                yield connection
            except Exception as e:
                connection.rollback()
                raise e

    @contextlib.contextmanager
    def session(self) -> Generator[Session, None, None]: 
        if self.session_local is None:
            raise Exception("Manager is not initialized")
        db = self.session_local()
        try:
            yield db
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.commit() 
            db.close()


session_manager = SessionManager(
    settings.getSqlalchemyURL(), 
    echo = settings.ECHO_SQL,
    pool_pre_ping=True, 
    pool_size=15, 
    max_overflow=20,
    pool_timeout=30, 
    pool_recycle=3600,
)
    
    
class AsyncSessionManager:
    def __init__(self, host: str, **engine_kwargs):
        self.engine = create_async_engine(host, **engine_kwargs)
        self.session_local = sessionmaker(autocommit=False, bind=self.engine, class_=AsyncSession)
        
    async def close(self):
        if self.engine is None:
            warnings.warn("Manager is not initialized")
            return
        await self.engine.dispose()
        self.engine = None
        self.session_local = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncSession, None]:
        if self.engine is None:
            raise Exception("Manager is not initialized")
        async with self.engine.begin() as connection:
            try:
                yield connection
            except Exception as e:
                await connection.rollback()
                raise e

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self.session_local is None:
            raise Exception("Manager is not initialized")
        db = self.session_local()
        try:
            yield db
        except Exception as e:
            await db.rollback()
            raise e
        finally:
            await db.commit() 
            await db.close()

    async def create_table(self, db_base):
        async with self.connect() as conn:
            await conn.run_sync(db_base.metadata.create_all) 

                                 
async_session_manager = AsyncSessionManager(
    settings.getSqlalchemyURL(), 
    echo = settings.ECHO_SQL,
    poolclass=NullPool,  
)