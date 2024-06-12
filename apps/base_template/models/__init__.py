from db.base_class import Base
from db.session import async_session_manager
from utils.async_utils import run_async
from .model_base import BaseTemplate


__all__ = ['BaseTemplate']


# Base.metadata.create_all(engine)
# run_async(async_session_manager.create_table(Base))