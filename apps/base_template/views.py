from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .schemas import *


from common import deps, error_code

from common.resp import respSuccessJson, respErrorJson

from core import constants

router = APIRouter()

@router.get("/", summary="")
async def get(*,
              db: Session = Depends(deps.get_db),
              ):
    return respSuccessJson()

