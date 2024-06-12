from contextlib import asynccontextmanager, contextmanager
from typing import Generator, Optional
from fastapi import FastAPI
from pymongo import MongoClient, database

from core.config import settings

        
def get_mongo(db_name: str = settings.MONGODB_DB_NAME) -> database.Database:
    """
    get_mongo 获取MongoDB数据库连接

    :param str db_name: 选择的数据库名称 
    :return database.Database:
    """
    if not settings.MONGODB_HOST:
        return None
    return MongoClient(settings.getMongoURL())[db_name or "db"]


@contextmanager        
def mongo_manager(db_name: str = settings.MONGODB_DB_NAME) -> Generator[Optional[database.Database], None, None]:
    mongodb_client = None if not settings.MONGODB_HOST else MongoClient(
        settings.getMongoURL(), serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    if mongodb_client:
        yield mongodb_client[db_name or "db"]
        mongodb_client.close()
    else:
        yield None