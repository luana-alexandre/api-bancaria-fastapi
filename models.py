from sqlalchemy import String, Float, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    senha: Mapped[str] = mapped_column(String(200))

    contas: Mapped[list["Conta"]] = relationship(back_populates="usuario")


class Conta(Base):
    __tablename__ = "contas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    saldo: Mapped[float] = mapped_column(Float, default=0)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    usuario: Mapped["Usuario"] = relationship(back_populates="contas")
    transacoes: Mapped[list["Transacao"]] = relationship(back_populates="conta")


class Transacao(Base):
    __tablename__ = "transacoes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    valor: Mapped[float] = mapped_column(Float)
    data: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    conta_id: Mapped[int] = mapped_column(ForeignKey("contas.id"))

    conta: Mapped["Conta"] = relationship(back_populates="transacoes")