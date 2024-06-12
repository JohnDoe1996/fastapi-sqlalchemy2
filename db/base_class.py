from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import InstrumentedAttribute, properties 
from sqlalchemy.sql import func, cast
from sqlalchemy.ext.declarative import as_declarative, declared_attr

from core.config import settings
from utils.transform import camel_case_2_underscore


def dt2ts(col: Column, label: str = None):
    """
    使用原生SQL把数据库时间转换为时间戳(使用时间戳解决时区问题)
    :param column:  type: Column    需要转换的数据库日期字段
    :param label:   type: string    转后时间戳的的字段名(相当于 sql 中的 AS )
    """
    # ts = func.strftime('%%s', col)  # sqlite
    # ts = cast(func.date_part('EPOCH', col), Integer) # pgsql
    ts = func.unix_timestamp(col) # mysql
    return ts.label(label) if label else ts


def ts2dt(col: Column, label: str = None):
    """
    ts2dt 使用原生sql把时间戳转为时间输出， 参数同上
    """
    # dt = func.datetime(col,'unixepoch')  # sqlite
    # dt =  func.to_timestamp(col)    # pgsql
    dt = func.from_unixtime(col)  # mysql
    return dt.label(label) if label else dt



@as_declarative()
class Base:
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_time = Column('created_time', DateTime, key='created_ts', default=func.now(), 
                          server_default=func.now(), comment="创建时间")
    creator_id = Column(Integer, default=0, server_default='0', comment="创建人id")
    modified_time = Column("modified_time", DateTime, key="modified_ts", default=func.now(), onupdate=func.now(), 
                         server_default=func.now(), server_onupdate=func.now(), comment="更新时间")
    modifier_id = Column(Integer, default=0, server_default='0', comment="修改人id")
    is_deleted = Column(Integer, default=0, comment="逻辑删除:0=未删除,1=删除", server_default='0')

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        # 如果没有指定__tablename__  则默认使用model类名转换表名字
        return (settings.SQL_TABLE_PREFIX or "") + camel_case_2_underscore(cls.__name__)

    @classmethod
    def list_columns(cls):
        """
        列出所有字段
        """
        return [getattr(cls, i) for i in dir(cls) if isinstance(getattr(cls, i), InstrumentedAttribute) 
                and isinstance(getattr(cls, i).comparator, properties.ColumnProperty.Comparator)]
        
    @property
    def _mapping(self):
        return self.to_dict()

    def to_dict(self, dict_name_use_key: bool = True):
        return {(c.key if dict_name_use_key else c.name): getattr(self, c.key, None) 
                for c in self.__table__.columns}

    def to_list(self):
        return [getattr(self, c.key, None) for c in self.__table__.columns]
