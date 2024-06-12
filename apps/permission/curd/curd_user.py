from typing import List

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, desc, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from common.curd_base import CRUDBase
from common.security import get_password_hash   
from ..models import Roles
from ..models.user import Users, UserRole


class CURDUser(CRUDBase):
    def init(self):
        self.exclude_columns.append(self.model.hashed_password)  # 排除掉密码字段

    async def get(self, db: AsyncSession, _id: int, to_dict: bool = True):
        """ 通过id获取 """
        user = (await db.execute(
            select(self.model).where(self.model.id == _id, self.model.is_deleted == 0)
            .options(selectinload(self.model.user_role))
        )).scalar()     # type: Users
        return  user if not (user and to_dict) else {
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname,
            'phone': user.phone,
            'email': user.email,
            'sex': user.sex,
            'avatar': user.avatar,
            'is_active': user.is_active,
            'status': user.status,
            'is_superuser': user.is_superuser,
            'roles': [i.id for i in user.user_role]
        }

    async def create(self, db: AsyncSession, *, obj_in, creator_id: int = 0):
        roles = (await db.execute(
            select(Roles).where(Roles.id.in_(obj_in.roles))
        )).all()
        obj_in_data = obj_in if isinstance(obj_in, dict) else jsonable_encoder(obj_in)
        del obj_in_data['roles']
        if 'password' in obj_in_data:
            obj_in_data['hashed_password'] = get_password_hash(obj_in_data['password'])
            del obj_in_data['password']
        else:
            obj_in_data['hashed_password'] = ""
        obj_in_data['creator_id'] = creator_id
        db_obj = self.model(**obj_in_data)  # type: Users
        db_obj.user_role = roles
        await db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def change_password(self, db: AsyncSession, *, _id: int, new_password: str, updater_id: int = 0):
        # print(new_password)
        obj_in = {'hashed_password': get_password_hash(new_password)}
        return await super().update(db, _id=_id, obj_in=obj_in, modifier_id=updater_id)

    async def update(self, db: AsyncSession, *, _id: int, obj_in, updater_id: int = 0):
        obj_in_data = obj_in if isinstance(obj_in, dict) else jsonable_encoder(obj_in)
        del obj_in_data['roles']
        if 'password' in obj_in_data:
            obj_in_data['hashed_password'] = get_password_hash(obj_in_data['password'])
            del obj_in_data['password']
        res = await super().update(db, _id=_id, obj_in=obj_in_data, modifier_id=updater_id)
        if res:
            await self.set_user_roles(db, user_id=_id, role_ids=obj_in.roles, ctl_id=updater_id)
        return res

    async def set_user_roles(self, db: AsyncSession, *, user_id: int, role_ids: List[int], ctl_id: int = 0):
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        db_objs = [dict(creator_id=ctl_id, role_id=i, user_id=user_id) for i in role_ids]
        await db.execute(insert(UserRole).values(db_objs))
        await db.commit()

    async def get_roles(self, db: AsyncSession, _id: int):
        u = (await db.execute(select(Users).where(Users.id == _id))).scalar()  # type: Users
        return u.user_role if u else None

    async def set_user_is_active(self, db: AsyncSession, *, user_id: int, is_active: bool, modifier_id: int = 0):
        return await super().update(db, _id=user_id, obj_in={'is_active': is_active}, modifier_id=modifier_id)

    async def search(self, db: AsyncSession, *, _id: int = None, username: str = "", 
                    nickname: str = "", email: str = "", phone: str = "",
                    status: int = None, created_after_ts: int = None, created_before_ts: int = None,
                    page: int = 1, page_size: int = 25):
        filters = []
        if _id is not None:
            filters.append(self.model.id == _id)
        if status is not None:
            filters.append(self.model.status == status)
        if username:
            filters.append(self.model.username.like(f"%{username}%"))
        if nickname:
            filters.append(self.model.nickname.like(f"%{nickname}%"))
        if email:
            filters.append(self.model.email.like(f"{email}%"))
        if phone:
            filters.append(self.model.email.like(f"{phone}%"))
        if created_before_ts is not None:
            filters.append(func.unix_timestamp(self.model.created_time) <= created_before_ts)
        if created_after_ts is not None:
            filters.append(func.unix_timestamp(self.model.created_time) >= created_after_ts)
        user_data, total, _, _ = await self.get_multi(
            db, page=page, page_size=page_size, filters=filters, order_bys=[desc(self.model.id)])
        return {'results': user_data, 'total': total}


curd_user = CURDUser(Users)