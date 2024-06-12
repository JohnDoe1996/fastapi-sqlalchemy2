from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, Tuple
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import func, select, update, delete, insert
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from db.base_class import Base, dt2ts


ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


# START
""" 
    jsonable_encoder (类转字典) 的 custom_encoder 方法。有些数据类型通过jsonable_encoder后会转换成不符合需求的类型或报错。 (目前遇到这3个 后续遇到其他再添加)
eg: 
    # 遇到dict类型数据使用custom_encoder_dict_fn解析,即直接输出字典类型不然会报错。 遇到datetime类型使用custom_encoder_datetime2str_fn解析成符合mysql的字符串,不然会转成其他格式的字符串
    data = jsonable_encoder(obj_in, custom_encoder={dict: custom_encoder_dict_fn, datetime: custom_encoder_datetime2str_fn})   
"""
custom_encoder_dict_fn = lambda x : x
custom_encoder_datetime_fn = lambda x : x
custom_encoder_datetime2str_fn = lambda x : x.strftime("%Y-%m-%d %H:%M:%S")
# END


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):

    def __init__(self, model: Type[ModelType]):
        self.model = model
        self.query_columns = self.model.list_columns() # 取model中的有Column
        self.exclude_columns = [
            self.model.created_time, self.model.modified_time, self.model.is_deleted]
        self.query_columns.extend((dt2ts(self.model.created_time, "created_ts"),
                                   dt2ts(self.model.modified_time, "modified_ts")))
        self.init()
        for ex in self.exclude_columns:
            self.query_columns.remove(ex)


    def init(self):
        """
        继承后用作数据初始化处理
        :return:
        """
        pass

    async def get(self, db: AsyncSession, _id: int, 
                  to_dict: bool = True) -> Union[ModelType, dict]:
        """ 通过id获取 """
        # # 模型的方式查询  未找到在sql层面排除掉不需要字段的方法
        # obj = (await db.execute(
        #     select(self.model).where(self.model.id == _id, self.model.is_deleted == 0)
        # )).scalar()  # type: Base
        # 字段的方式查询
        obj = (await db.execute(
            select(*self.query_columns).where(self.model.id == _id, self.model.is_deleted == 0)
        )).first()   # type: Row
        return dict(obj._mapping) if obj and to_dict else obj

    async def query(self, db: AsyncSession, *, queries: Optional[list] = None, 
                    filters: Optional[list] = None, order_bys: Optional[list] = None, 
                    to_dict: bool = True) -> List[ModelType]:
        """ 查询 """
        filters = (filters or []) + [self.model.is_deleted == 0]
        queries = queries or self.query_columns
        sql = select(*queries).where(*filters)
        if order_bys:
            sql.order_by(*order_bys)
        obj = (await db.execute(sql)).all()
        return [dict(i._mapping) for i in obj] if obj and to_dict else obj

    async def get_multi(self, db: AsyncSession, *, queries: Optional[list] = None, 
                        filters: Optional[list] = None, order_bys: Optional[list] = None, 
                        page: int = 1, page_size: int = 25, to_dict: bool = True
                       ) -> Tuple[List[ModelType], int, int, int]:
        """
        分页查询
        :return (data, total, offset, limit)
        """
        filters = (filters or []) + [self.model.is_deleted == 0]
        queries = queries or self.query_columns
        sql = select(*queries).where(*filters)
        if order_bys:
            sql.order_by(*order_bys)
        temp_page = ((page if page > 0 else 1) - 1) * page_size
        total = (await db.execute(select(func.count(self.model.id)).where(*filters))).scalar()
        if temp_page + page_size > total:   # 页数超出后显示最后一页， 不需要可以注释掉
            temp_page = total - (total % page_size)
        sql = sql.offset(temp_page).limit(page_size)
        obj = (await db.execute(sql)).all()
        return [dict(i._mapping) for i in obj] if  obj and to_dict else obj, total, temp_page, page_size

    async def create(self, db: AsyncSession, *, obj_in: Union[CreateSchemaType, Dict[str, Any]], 
                     creator_id: int = 0, commit: bool = True) -> Union[List[int], int]:
        """ 创建 """
        if isinstance(obj_in, (tuple, list)):
            obj_in_data = []
            for _obj_in in obj_in:
                _obj_in_data = jsonable_encoder(
                    _obj_in, custom_encoder={dict: custom_encoder_dict_fn})
                _obj_in_data['creator_id'] = creator_id
                obj_in_data.append(_obj_in_data)
            result = (await db.execute(
                insert(self.model).values(obj_in_data).returning(self.model.id))).scalars().all()
        else:
            obj_in_data = jsonable_encoder(obj_in, custom_encoder={dict: custom_encoder_dict_fn})
            obj_in_data['creator_id'] = creator_id
            result = (await db.execute(
                insert(self.model).values(**obj_in_data).returning(self.model.id))).scalar()  
        if commit:
            await db.commit()
        return result 

    async def update(self, db: AsyncSession, *, _id: Union[int, List[int]], 
                     obj_in: Union[UpdateSchemaType, Dict[str, Any]],
                     modifier_id: int = 0, commit: bool = True) -> int:
        """ 更新 """
        update_data = jsonable_encoder(obj_in, custom_encoder={dict: custom_encoder_dict_fn})
        update_data['modifier_id'] = modifier_id
        update_data = {getattr(self.model, k): v for k, v in update_data.items() if hasattr(self.model, k)}
        sql = update(self.model).values(update_data).where(self.model.is_deleted != 1)
        if isinstance(_id, (list, tuple, set)):
            sql = sql.where(self.model.id.in_(_id))
        else:
            sql = sql.where(self.model.id == int(_id))
        res = (await db.execute(sql)).merge()
        if commit:
            await db.commit()
        return res.rowcount

    async def delete(self, db: AsyncSession, *, _id: Union[int, List[int]], 
                     deleter_id: int = 0, commit: bool = True) -> int:
        """ 逻辑删除 """
        update_data = {self.model.is_deleted: 1}
        if deleter_id:
            update_data[self.model.modifier_id] = deleter_id
        sql = update(self.model).values(update_data).where(self.model.is_deleted != 1)
        if isinstance(_id, (list, tuple, set)):
            sql = sql.where(self.model.id.in_(_id))
        else:
            sql = sql.where(self.model.id == int(_id))
        res = (await db.execute(sql)).merge()
        if commit:
            await db.commit()
        return res.rowcount

    async def remove(self, db: AsyncSession, *, _id: Union[int, List[int]],
                     commit: bool = True) -> int:
        """ 物理删除 """
        sql = delete(self.model)
        if isinstance(_id, (list, tuple, set)):
            sql = sql.where(self.model.id.in_(_id))
        else:
            sql = sql.where(self.model.id == int(_id))
        res = (await db.execute(sql)).merge()
        if commit:
            await db.commit()
        return res.rowcount

    async def get_max_order_num(self, db: AsyncSession) -> int:
        data = (await db.execute(
            select(func.max(self.model.order_num).label('max_order_num'))
            .where(self.model.is_deleted == 0)
        )).first()
        return data[0] if data and data else 0

