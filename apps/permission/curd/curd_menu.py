from typing import Optional, Tuple, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, select
from common.curd_base import CRUDBase
from db.base_class import dt2ts
from ..models.menu import Menus


class CURDMenu(CRUDBase):
    async def query_menus(self, db: AsyncSession, status: int = None, title: str = None):
        queries = [self.model.id, self.model.title, self.model.icon, self.model.parent_id,
                   self.model.order_num, self.model.status, self.model.component, self.model.path,
                   dt2ts(self.model.created_time, "created_ts"),
                   dt2ts(self.model.modified_time, "modified_ts")]
        filters = []
        if title:
            filters.append(Menus.title.like(f"%{title}%"))
        if status is not None:
            filters.append(Menus.status == status)
        res = await self.query(db, queries=queries, filters=filters, order_bys=[asc(Menus.order_num)])
        return res

    async def get_simple_list(self, db: AsyncSession, *, status_in: List[int] = None, 
                              to_dict: bool = True) -> list:
        status_in = status_in or (0,)
        obj = (await db.execute(
            select(self.model.id, self.model.title, self.model.parent_id)
            .where(self.model.is_deleted == 0, self.model.status.in_(status_in))
            .order_by(asc(self.model.order_num))
        )).all() 
        return [dict(i) for i in obj.all()] if to_dict else obj.all()

    async def get_simple_tree(self, db: AsyncSession, *, status_in: List[int] = None) -> List[dict]:
        status_in = status_in or (0,)

        async def __get_children(parent_id: int = 0) -> List[dict]:
            filters = (self.model.parent_id == parent_id, 
                       self.model.is_deleted == 0, 
                       self.model.status.in_(status_in))
            res = (await db.execute(
                select(self.model.id, self.model.title).where(*filters).order_by(asc(self.model.order_num))
            )).all()
            return [{'id': i['id'], 'title': i['title'], 
                     'children': await __get_children(i['id'])} for i in res]
        return await __get_children()

    async def get_max_order_num(self, db: AsyncSession, parent_id: int = None) -> int:
        filters = (self.model.is_deleted == 0,) if parent_id is None else (self.model.parent_id == parent_id,
                                                                          self.model.is_deleted == 0)
        data = (await db.execute(
            select(func.max(self.model.order_num).label('max_order_num')).where(*filters)
        )).first()
        return data['max_order_num'] if data else 0


curd_menu = CURDMenu(Menus)