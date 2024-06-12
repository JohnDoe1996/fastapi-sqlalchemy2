from typing import List
from sqlalchemy import distinct, desc, asc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from apps.permission.models.menu import Menus
from apps.permission.models.role import RoleMenu, Roles
from apps.permission.models.user import Users, UserRole
from apps.system.models import ConfigSettings
from common.curd_base import CRUDBase
from common.security import verify_password, get_password_hash
from fastapi.encoders import jsonable_encoder


class CURDUser(CRUDBase):
    async def get_by_username(self, db: AsyncSession, *, username: str):
        """
        通过用户名获取用户
        """
        return (await db.execute(select(Users).where(Users.username == username))).scalar()

    async def get_by_email(self, db: AsyncSession, *, email: str):
        """
        通过email获取用户
        """
        return (await db.execute(select(Users).where(Users.email == email))).scalar()

    async def get_by_phone(self, db: AsyncSession, *, phone: str):
        """
        通过手机号获取用户
        """
        return (await db.execute(select(Users).where(Users.phone == phone))).scalar()

    async def authenticate(self, db: AsyncSession, *, user: str, password: str):
        if user.find("@") > 0:
            u = await self.get_by_email(db, email=user)
        elif user.startswith('1') and user.isdigit():
            u = await self.getByPhone(db, phone=user)
        else:
            u = await self.get_by_username(db, username=user)
        if not u:
            return None
        if not verify_password(password, u.hashed_password):
            return None
        return u

    async def check_username_availability(self, db: AsyncSession, *, username: str, exclude_id: int = None):
        sql = select(func.count(self.model.id).label('count')).where(
            self.model.is_deleted == 0, self.model.username == username)
        if exclude_id:
            sql = sql.where(self.model.id != exclude_id)
        return (await db.execute(sql)).scalar() == 0

    async def check_email_availability(self, db: AsyncSession, *, email: str, exclude_id: int = None):
        sql = select(func.count(self.model.id).label('count')).where(
            self.model.is_deleted == 0, self.model.email == email)
        if exclude_id:
            sql = sql.where(self.model.id != exclude_id)
        return (await db.execute(sql)).scalar() == 0

    async def check_phone_availability(self, db: AsyncSession, *, phone: str, exclude_id: int = None):
        sql = select(func.count(self.model.id).label('count')).where(
            self.model.is_deleted == 0, self.model.phone == phone)
        if exclude_id:
            sql = sql.where(self.model.id != exclude_id)
        return (await db.execute(sql)).scalar() == 0

    async def create(self, db: AsyncSession, *, obj_in, creator_id: int = 0):
        obj_in_data = jsonable_encoder(obj_in)
        obj_in_data['hashed_password'] = get_password_hash(obj_in_data['password'])
        del obj_in_data['password']
        init_roles = db.query(ConfigSettings.value).filter(
            ConfigSettings.key == 'user_init_roles', ConfigSettings.is_deleted == 0, ConfigSettings.status == 0
        ).first()
        if init_roles:
            init_roles_key = init_roles.value.split(',')
            obj_in_data['user_role'] = db.query(Roles).filter(
                Roles.key.in_(init_roles_key), Roles.is_deleted == 0).all()
        return await super().create(db, obj_in=obj_in_data, creator_id=creator_id)

    async def get_roles(self, db: AsyncSession, _id: int):
        obj = (await db.execute(
            select(Users).where(Users.id == _id).options(selectinload(self.model.user_role))
        )).scalar()  # type: Users
        return obj.user_role if obj else None

    async def get_menus_id_in(self, db: AsyncSession, _id: int) -> List[int]:
        return (await db.execute(
            select(distinct(RoleMenu.menu_id).label('id'))
            .join(Roles, Roles.id == RoleMenu.role_id)
            .join(UserRole, Roles.id == UserRole.role_id)
            .where(UserRole.user_id == _id, Roles.is_deleted == 0, RoleMenu.is_deleted == 0)
        )).scalars().all()  
        
    async def get_menus(self, db: AsyncSession, _id: int = None):
        menu_id_in = _id and await self.get_menus_id_in(db, _id)
        sql = select(
            Menus.id, Menus.path, Menus.name, Menus.icon, Menus.parent_id, Menus.is_frame, Menus.title,
            Menus.no_cache, Menus.component, Menus.hidden
        ).where(Menus.is_deleted == 0,  Menus.status == 0)
        if menu_id_in:
            sql = sql.where(Menus.id.in_(menu_id_in))
        res = (await db.execute(sql.order_by(asc(Menus.order_num)))).all()
        return [{
            'id': i.id,
            'parent_id': i.parent_id,
            'path': i.path,
            'component': i.component,
            'is_frame': i.is_frame,
            'hidden': i.hidden,
            'name': i.name,
            'meta': {
                'title': i.title,
                'icon': i.icon,
                'no_cache': i.no_cache,
            }
        } for i in res]

    async def get_menus_tree(self, db: AsyncSession, _id: int = None):
        menu_id_in = _id and await self.get_menus_id_in(db, _id)
        
        async def __get_children_menus(menu_id: int = 0):
            sql = select(
                Menus.id, Menus.path, Menus.name, Menus.icon, Menus.parent_id, Menus.is_frame, Menus.title,
                Menus.no_cache, Menus.component, Menus.hidden
            ).where(
                Menus.is_deleted == 0, Menus.parent_id == menu_id, Menus.id.in_(menu_id_in), Menus.status == 0
            )
            if menu_id_in:
                sql = sql.where(Menus.id.in_(menu_id_in))
            children = (await db.execute(sql.order_by(asc(Menus.order_num)))).all()
            result = []
            for child in children:
                result.append({
                    'path': child['path'],
                    'component': child['component'],
                    'is_frame': child['is_frame'],
                    'hidden': child['hidden'],
                    'name': child['name'],
                    'meta': {
                        'title': child['title'],
                        'icon': child['icon'],
                        'no_cache': child['no_cache'],
                    },
                    'children': __get_children_menus(child['id'])
                })
            return result
        return await __get_children_menus()

    async def set_avatar(self, db: AsyncSession, _id: int, avatar_path: str, modifier_id: int = 0):
        update_data = {self.model.avatar: avatar_path}
        if modifier_id:
            update_data['modifier_id'] = modifier_id
        await db.execute(update(self.model).values(**update_data)
                        .where(self.model.id == _id, self.model.is_deleted == 0))
        await db.commit()

    async def check_pwd(self, db: AsyncSession, _id: int, *, pwd: str) -> bool:
        hashed_password = (await db.execute(
            select(self.model.hashed_password).where(self.model.id == _id, self.model.is_deleted == 0)
        )).scalar()
        return bool(hashed_password and verify_password(pwd, hashed_password))

    async def change_pwd(self, db: AsyncSession, _id: int, *, pwd: str):
        update_data = {self.model.hashed_password: get_password_hash(pwd)}
        await db.execute(update(self.model).values(**update_data)
                         .where(self.model.id == _id, self.model.is_deleted == 0))
        await db.commit()


curd_user = CURDUser(Users)