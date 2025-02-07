import json
from datetime import timedelta
from typing import Optional, Tuple, List, Union

from sqlalchemy.ext.asyncio import AsyncSession
try:
    from redis.asyncio import Redis
except ImportError:
    from aioredis import Redis
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, distinct, select, insert
from common.curd_base import CRUDBase
from core import constants
from ..models import Roles, UserRole
from ..models.perm_label import PermLabel, PermLabelRole


class CURDPermLabel(CRUDBase):

    async def get(self, db: AsyncSession, _id: int, to_dict: bool = True):
        """ 通过id获取 """
        label = (await db.execute(
            select(self.model).where(self.model.id == _id, self.model.is_deleted == 0)
        )).scalar()
        return label if not (label and to_dict) else {
            'id': label.id,
            'label': label.label,
            'remark': label.remark,
            'status': label.status,
            'roles': [i.id for i in label.label_role]
        }

    async def create(self, db: AsyncSession, *, obj_in, creator_id: int = 0):
        obj_in_data = obj_in if isinstance(obj_in, dict) else jsonable_encoder(obj_in)
        if (await db.execute(
            select(self.model)
            .where(self.model.label == obj_in_data['label'], self.model.is_deleted == 0)
        )).scalar():
            return None
        roles = (await db.execute(
            select(Roles).where(Roles.id.in_(obj_in_data.get('roles', [])))
        )).all()
        if 'roles' in obj_in_data:
            del obj_in_data['roles']
        obj_in_data['creator_id'] = creator_id
        db_obj = self.model(**obj_in_data)  # type: PermLabel
        db_obj.label_role = roles
        await db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, _id: int, obj_in, updater_id: int = 0):
        print(obj_in.roles)
        obj_in_data = obj_in if isinstance(obj_in, dict) else jsonable_encoder(obj_in)
        del obj_in_data['roles']
        res = await super().update(db, _id=_id, obj_in=obj_in_data, modifier_id=updater_id)
        if res:
            await self.set_label_roles(db, label_id=_id, role_ids=obj_in.roles, ctl_id=updater_id)
        return res

    async def search(self, db: AsyncSession, *, label: str = "", remark: str = "", 
                     status: int = None, page: int = 1, page_size: int = 25) -> dict:
        filters = []
        if status is not None:
            filters.append(self.model.status == status)
        if label:
            filters.append(self.model.label.like(f"%{label}%"))
        if remark:
            filters.append(self.model.remark.like(f"%{remark}%"))
        user_data, total, _, _ = await self.get_multi(db, page=page, page_size=page_size, filters=filters)
        return {'results': user_data, 'total': total}

    async def set_label_roles(self, db: AsyncSession, *, label_id: int, role_ids: List[int], ctl_id: int = 0):
        db.query(PermLabelRole).filter(PermLabelRole.label_id == label_id).delete()
        db_objs = [PermLabelRole(creator_id=ctl_id, role_id=i, label_id=label_id) for i in role_ids]
        await db.add_all(db_objs)
        await db.commit()
        
    async def get_labels_by_roles_id(self, db: AsyncSession, roles_id: Union[Tuple[int], List[int]]):
        status_in = (0,)
        perm_labels = [perm.label for perm in (await db.execute(
            select(distinct(self.model.label).label('label'))
            .join(PermLabelRole, isouter=True)
            .where(PermLabelRole.role_id.in_(roles_id), self.model.status.in_(status_in),
                   Roles.is_deleted == 0, PermLabelRole.is_deleted == 0)
        )).all()] if roles_id is not None else []
        return perm_labels

    async def get_labels_role_ids(self, db: AsyncSession, *, labels: Tuple[str], redis: Redis = None):
        if redis:
            # if res := await redis.get(constants.REDIS_KEY_USER_PERM_LABEL_CACHE + labels)   # python3.8+
            res = await redis.get(constants.REDIS_KEY_USER_PERM_LABEL_CACHE + '_'.join(labels))
            if res:
                return json.loads(res.decode('utf-8'))
        status_in = (0,)
        res = [r['id'] for r in (await db.execute(
            select(distinct(PermLabelRole.role_id).label('id'))
            .join(self.model, self.model.id == PermLabelRole.label_id)
            .where(self.model.label.in_(labels), self.model.status.in_(status_in),
                   Roles.is_deleted == 0, PermLabelRole.is_deleted == 0)
        )).all()]
        if redis:
            await redis.setex(constants.REDIS_KEY_USER_PERM_LABEL_CACHE + '_'.join(labels),
                              timedelta(minutes=constants.USER_PERM_LABEL_CACHE_EXPIRE_MINUTES),
                              json.dumps(res))
        return res


curd_perm_label = CURDPermLabel(PermLabel)