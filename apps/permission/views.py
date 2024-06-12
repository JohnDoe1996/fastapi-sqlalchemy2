import os

from fastapi import APIRouter, Depends, Query, File, UploadFile
from sqlalchemy.orm import Session
from utils.encrypt import get_uuid
from .models import Users
from .schemas import *
from .curd.curd_user import curd_user
from .curd.curd_role import curd_role
from .curd.curd_menu import curd_menu
from .curd.curd_perm_label import curd_perm_label

from common import deps, error_code

from common.resp import respSuccessJson, respErrorJson

from core import constants

router = APIRouter()


@router.get("/user/{user_id}", summary="获取用户信息")
async def get_user(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:user:get", "perm:user:put"])),
                    user_id: int,
                    ):
    return respSuccessJson(await curd_user.get(db, user_id))


@router.get("/user", summary="获取用户列表")
async def list_user(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:user:get"])),
                    id: int = Query(None, gt=0),
                    username: str = Query(""),
                    nickname: str = Query(""),
                    email: str = Query(""),
                    phone: str = Query(""),
                    status: int = Query(None),
                    created_after_ts: int = None,
                    created_before_ts: int = None,
                    page: int = Query(1, gt=0),
                    page_size: int = Query(20, gt=0),
                    ):
    return respSuccessJson(await curd_user.search(
        db, _id=id, username=username, nickname=nickname, email=email, phone=phone, 
        status=status, created_after_ts=created_after_ts, created_before_ts=created_before_ts,
        page=page, page_size=page_size))


@router.post("/user", summary="添加用户")
async def add_user(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:user:post"])),
                    obj: UserSchema,
                    ):
    await curd_user.create(db, obj_in=obj, creator_id=u['id'])
    return respSuccessJson()


@router.post("/user/file/avatar", summary="上传头像照片")
async def upload_avatar(img: UploadFile):
    img_data = img.file.read()
    img_name = img.filename  # type: str
    new_img_name = f"{get_uuid()}.{img_name.split('.')[-1]}"
    path = constants.MEDIA_AVATAR_BASE_DIR + new_img_name
    with open(os.path.join(constants.MEDIA_BASE_PATH, path), 'wb') as f:
        f.write(img_data)
    return respSuccessJson({'path': path})


@router.put("/user/{user_id}/password", summary="修改指定用户的密码")
async def set_password(*,
                        user_id: int,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:user:put"])),
                        obj: UserSetPasswordSchema
                        ):
    await curd_user.change_password(db, _id=user_id, new_password=obj.password, updater_id=u['id'])
    return respSuccessJson()


@router.put("/user/{user_id}/active", summary="修改用户是否活跃的状态")
async def set_is_active(*,
                        user_id: int,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:user:get"])),
                        obj: UserIsActiveSchema
                        ):
    await curd_user.set_user_is_active(db, user_id=user_id, is_active=obj.is_active, modifier_id=u['id'])
    return respSuccessJson()


@router.put("/user/{user_id}", summary="修改用户信息")
async def set_user(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:user:put"])),
                    obj: UserSchema,
                    user_id: int,
                    ):
    await curd_user.update(db, _id=user_id, obj_in=obj, updater_id=u['id'])
    return respSuccessJson()


@router.put("/user/{user_id}/roles", summary="修改用户角色")
async def set_user_roles(*,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:user:put"])),
                        obj: UserRolesSchema,
                        user_id: int,
                        ):
    await curd_user.set_user_roles(db, user_id=user_id, role_ids=obj.roles, ctl_id=u['id'])
    return respSuccessJson()


@router.delete("/user/{user_id}", summary="删除用户")
async def del_user(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:user:delete"])),
                    user_id: int,
                    ):
    await curd_user.delete(db, _id=user_id, deleter_id=u['id'])
    return respSuccessJson()


@router.get("/role", summary="获取所有权限角色")
async def list_role(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:role:get"])),
                    key: str = Query(""),
                    name: str = Query(""),
                    status: int = Query(None),
                    page: int = Query(1, gt=0),
                    page_size: int = Query(25, gt=0),
                    ):
    return respSuccessJson(await curd_role.search(
        db, name=name, key=key, status=status, page=page, page_size=page_size))


@router.get("/role/select/list", summary="获取权限角色选择列表")
async def get_role_select_list(*,
                                db: Session = Depends(deps.get_db)
                                ):
    return respSuccessJson({'roles': await curd_role.get_select_list(db)})


@router.get("/role/max-order-num", summary="获取权限最大排序")
async def get_role_max_order_num(*,
                                db: Session = Depends(deps.get_db)
                                ):
    return respSuccessJson({'max_order_num': await curd_role.get_max_order_num(db)})


@router.get("/role/{role_id}", summary="查看单个权限角色")
async def get_role(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:role:get"])),
                    role_id: int
                    ):
    return respSuccessJson(await curd_role.get(db, _id=role_id))


@router.post("/role", summary="添加权限角色")
async def add_role(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:role:post"])),
                    obj: RoleSchema
                    ):
    await curd_role.create(db, obj_in=obj, creator_id=u['id'])
    return respSuccessJson()


@router.put("/role/{role_id}", summary="修改角色权限")
async def set_role(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:role:put"])),
                    role_id: int,
                    obj: RoleSchema
                    ):
    await curd_role.update(db, _id=role_id, obj_in=obj, modifier_id=u['id'])
    return respSuccessJson()


@router.put("/role/{role_id}/users", summary="修改角色用户")
async def set_role_users(*,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:role:put"])),
                        role_id: int,
                        obj: RoleUsersSchema
                        ):
    await curd_role.set_role_users(db, role_id=role_id, user_ids=obj.users, ctl_id=u['id'])
    return respSuccessJson()


@router.delete("/role/{role_id}", summary="删除角色权限")
async def del_role(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:role:delete"])),
                    role_id: int
                    ):
    await curd_role.delete(db, _id=role_id, deleter_id=u['id'])
    return respSuccessJson()


@router.get("/menu", summary="菜单列表")
async def list_menus(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:menu:get"])),
                    title: str = Query(""),
                    status: int = Query(None)
                    ):
    return respSuccessJson({'menus': await curd_menu.query_menus(db, status, title)})


@router.get("/menu/simple/list", summary="获取简易结构的菜单列表")
async def get_menu_simple_list(*,
                                db: Session = Depends(deps.get_db),
                                u: Users = Depends(deps.user_perm(["perm:menu:get"])),
                                ):
    return respSuccessJson({'menus': await curd_menu.get_simple_list(db)})


@router.get("/menu/simple/tree", summary="获取简易结构的菜单树状列表")
async def get_menu_simple_tree(*,
                                db: Session = Depends(deps.get_db),
                                u: Users = Depends(deps.user_perm(["perm:menu:get"])),
                                ):
    return respSuccessJson({'menus': await curd_menu.get_simple_tree(db)})


@router.get("/menu/{menu_id}", summary="单个菜单")
async def get_menu(*,
                    menu_id: int,
                    u: Users = Depends(deps.user_perm(["perm:menu:get", "perm:menu:gut"])),
                    db: Session = Depends(deps.get_db)
                    ):
    return respSuccessJson(await curd_menu.get(db, _id=menu_id))


@router.post("/menu", summary="添加菜单")
async def add_menu(*,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:menu:post"])),
                    obj: MenuSchema
                    ):
    await curd_menu.create(db, obj_in=obj, creator_id=u['id'])
    return respSuccessJson()


@router.put("/menu/{menu_id}", summary="修改菜单")
async def set_menu(*,
                    menu_id: int,
                    db: Session = Depends(deps.get_db),
                    u: Users = Depends(deps.user_perm(["perm:menu:put"])),
                    obj: MenuSchema
                    ):
    await curd_menu.update(db, _id=menu_id, obj_in=obj, modifier_id=u['id'])
    return respSuccessJson()


@router.delete("/menu/{menu_id}", summary="删除菜单")
async def del_menu(*,
                    menu_id: int,
                    u: Users = Depends(deps.user_perm(["perm:menu:delete"])),
                    db: Session = Depends(deps.get_db)
                    ):
    await curd_menu.delete(db, _id=menu_id, deleter_id=u['id'])
    return respSuccessJson()


@router.get("/menu/{parent_menu_id}/max-order-num", summary="获取菜单最大排序")
async def get_menu_max_order_num(*,
                                parent_menu_id: int,
                                db: Session = Depends(deps.get_db)
                                ):
    return respSuccessJson({
        'max_order_num': await curd_menu.get_max_order_num(db, parent_id=parent_menu_id)})


@router.put("/role/{role_id}/menu", summary="修改权限对应的菜单")
async def set_role_menu(*,
                        role_id: int,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:menu:put", "perm:role:put"])),
                        obj: RoleMenuSchema
                        ):
    await curd_role.set_role_menu(db, role_id, obj.menu_ids, ctl_id=u['id'])
    return respSuccessJson()


@router.get("/perm-label", summary="获取权限标识")
async def list_perm_label(*,
                            db: Session = Depends(deps.get_db),
                            u: Users = Depends(deps.user_perm(["perm:label:get"])),
                            status: int = Query(None),
                            label: str = Query(None),
                            remark: str = Query(None),
                            page: int = Query(1, gt=0),
                            page_size: int = Query(20, gt=0),
                            ):
    res = await curd_perm_label.search(
        db, label=label, remark=remark, status=status, page=page, page_size=page_size)
    return respSuccessJson(res)


@router.get("/perm-label/{_id}", summary="通过ID获取权限标识")
async def get_perm_label(*,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:label:get", "perm:label:put"])),
                        _id: int,
                        ):
    return respSuccessJson(await curd_perm_label.get(db, _id=_id))


@router.post("/perm-label", summary="添加权限标识")
async def add_perm_label(*,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:label:post"])),
                        obj: PremLabelSchema,
                        ):
    res = await curd_perm_label.create(db, obj_in=obj, creator_id=u['id'])
    if res:
        return respSuccessJson()
    return respErrorJson(error=error_code.ERROR_USER_PREM_ADD_ERROR)


@router.put("/perm-label/{_id}", summary="修改权限标识")
async def set_per_label(*,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:label:put"])),
                        _id: int,
                        obj: PremLabelSchema,
                        ):
    await curd_perm_label.update(db, _id=_id, obj_in=obj, updater_id=u['id'])
    return respSuccessJson()


@router.delete("/perm-label/{_id}", summary="删除权限标识")
async def del_perm_label(*,
                        db: Session = Depends(deps.get_db),
                        u: Users = Depends(deps.user_perm(["perm:label:delete"])),
                        _id: int,
                        ):
    await curd_perm_label.delete(db, _id=_id, deleter_id=u['id'])
    return respSuccessJson()
