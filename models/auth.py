from sqlmodel import SQLModel


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(SQLModel):
    sub: str
    rol: str
