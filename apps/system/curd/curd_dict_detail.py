from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import func, select
from common.curd_base import CRUDBase
from ..models.dictionaries import DictDetails, DictData


class CURDDictDetail(CRUDBase):
        
    async def get(self, db: AsyncSession, _id: int, to_dict: bool = True):
        """ 通过id获取 """
        obj = (await db.execute(
            select(*self.query_columns, DictData.dict_name, DictData.dict_type)
            .join(DictData, self.model.dict_data_id == DictData.id, isouter=True)    # join(..., isouter=True) == LEFT JOIN， join(...) == INNER JOIN， 不支持 RIGHT JOIN (可以考虑表顺序实现), 有外键的时候可以省略 指定关联字段即第二个参数
            .where(self.model.id == _id, self.model.is_deleted == 0)
        )).first()
        return dict(obj._mapping) if to_dict else obj
    
    async def get_max_order_num(self, db: AsyncSession, *, dict_data_id: int ) -> int:
        res = (await db.execute(
            select(func.max(DictDetails.order_num).label('max_order_num'))
            .where(DictDetails.dict_data_id == dict_data_id, DictDetails.is_deleted == 0)
        )).first()
        return res['max_order_num'] if res else 0


curd_dict_detail = CURDDictDetail(DictDetails)