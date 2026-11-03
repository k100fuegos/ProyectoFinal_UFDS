from typing import Annotated
from sqlmodel import Session
from config.db import get_session
from fastapi import Depends

SessionDeDependencia = Annotated[Session, Depends(get_session)]
