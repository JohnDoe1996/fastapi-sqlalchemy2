from typing import List

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from common.curd_base import CRUDBase, CreateSchemaType
from ..models.role import Roles, RoleMenu
from ..models.menu import Menus
from ..models.user import UserRole


class CURDRole(CRUDBase):

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType, creator_id: int = 0):
        menus = (await db.execute(
            select(Menus).where(Menus.id.in_(obj.menus))
        )).all()
        obj_in_data = obj_in if isinstance(obj_in, dict) else jsonable_encoder(obj_in)
        del obj_in_data['menus']
        obj_in_data['creator_id'] = creator_id
        obj = self.model(**obj_in_data)   # type: Roles
        obj.role_menu = menus
        await db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def get(self, db: AsyncSession, _id: int, to_dict: bool = True):
        role = (await db.execute(
            select(self.model).where(self.model.id == _id, self.model.is_deleted == 0)    
        )).scalar()
        return role if not to_dict else {
            'id': role.id,
            'key': role.key,
            'name': role.name,
            'order_num': role.order_num,
            'status': role.status,
            'menus': [{'id': i.id} for i in role.role_menu]
        }

    async def search(self, db: AsyncSession, *, key: str = "", name: str = "", 
                     status: int = None, page: int = 1, page_size: int = 25) -> dict:
        filters = []
        if status is not None:
            filters.append(self.model.status == status)
        if name:
            filters.append(self.model.name.like(f"%{name}%"))
        if key:
            filters.append(self.model.key.like(f"%{key}%"))
        user_data, total, _, _ = await self.get_multi(
            db, page=page, page_size=page_size, filters=filters)
        return {'results': user_data, 'total': total}

    async def set_role_menu(self, db: AsyncSession, role_id: int, menu_ids: List[int], 
                            *, ctl_id: int = 0):
        await db.execute(delete(RoleMenu).where(RoleMenu.role_id == role_id))
        db_objs = [{'creator_id': ctl_id, 'role_id': role_id, 'menu_id': menu_id} for menu_id in menu_ids]
        await db.execute(insert(RoleMenu).values(*db_objs))
        await db.commit()
        
    async def set_role_users(self, db: AsyncSession, *, role_id: int, user_ids: List[int], ctl_id: int = 0):
        await db.execute(delete(UserRole).where(UserRole.role_id == role_id))
        db_objs = [dict(creator_id=ctl_id, role_id=role_id, user_id=user_id) for user_id in user_ids]
        await db.execute(insert(UserRole).values(*db_objs))
        db.commit()

    async def get_select_list(self, db: AsyncSession, status_in: List[int] = None):
        status_in = status_in or (0, )
        return await self.query(db, queries=[self.model.id, self.model.key, self.model.name],
                                filters=[self.model.status.in_(status_in)], order_bys=[self.model.order_num])


curd_role = CURDRole(Roles)