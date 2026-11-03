from sqlmodel import SQLModel, Field


class LibroAutor(SQLModel, table=True):
    __tablename__ = "libro_autores"  # type: ignore
    libro_id: int = Field(
        foreign_key="libros.libro_id",
        primary_key=True,
        ondelete="CASCADE",
    )
    autor_id: int = Field(
        foreign_key="autores.autor_id",
        primary_key=True,
        ondelete="RESTRICT",
    )
