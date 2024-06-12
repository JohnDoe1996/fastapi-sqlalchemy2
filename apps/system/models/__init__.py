from db.base_class import Base
from db.session import async_session_manager
from utils.async_utils import run_async 
from .config_settings import ConfigSettings
from .dictionaries import DictData, DictDetails


__all__ = ['DictData', 'DictDetails', 'ConfigSettings']


# Base.metadata.create_all(engine)
run_async(async_session_manager.create_table(Base))