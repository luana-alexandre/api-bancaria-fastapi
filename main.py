from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from pydantic import BaseModel, EmailStr

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import Base, engine, AsyncSessionLocal
from models import Usuario, Conta, Transacao
from auth import (
    gerar_hash_senha,
    verificar_senha,
    criar_token,
    verificar_token
)


# =========================
# LIFESPAN
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


# =========================
# APP
# =========================

app = FastAPI(
    title="API Bancária Assíncrona",
    description="Desafio de API bancária com FastAPI, JWT, depósitos, saques e extrato.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def inicio():
    return {"mensagem": "API Bancária rodando com sucesso"}

# =========================
# PERSONALIZAÇÃO DE ERROS
# =========================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    return JSONResponse(
        status_code=422,
        content={
            "status": "erro",
            "mensagem": "Verifique os dados enviados.",
            "detalhes": exc.errors()
        },
    )


# =========================
# CONEXÃO COM O BANCO
# =========================

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# =========================
# SCHEMAS
# =========================

class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class Login(BaseModel):
    email: EmailStr
    senha: str


class TransacaoCreate(BaseModel):
    conta_id: int
    valor: float


# =========================
# CRIAR USUÁRIO
# =========================

@app.post("/usuarios")
async def criar_usuario(
    dados: UsuarioCreate,
    db: AsyncSession = Depends(get_db)
):
    resultado = await db.execute(
        select(Usuario).where(Usuario.email == dados.email)
    )

    usuario_existente = resultado.scalar_one_or_none()

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="E-mail já cadastrado"
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=gerar_hash_senha(dados.senha)
    )

    db.add(novo_usuario)

    await db.commit()
    await db.refresh(novo_usuario)

    nova_conta = Conta(
        usuario_id=novo_usuario.id,
        saldo=0
    )

    db.add(nova_conta)

    await db.commit()
    await db.refresh(nova_conta)

    return {
        "mensagem": "Usuário e conta criados com sucesso",
        "usuario_id": novo_usuario.id,
        "conta_id": nova_conta.id
    }


# =========================
# LOGIN
# =========================

@app.post("/login")
async def login(
    dados: Login,
    db: AsyncSession = Depends(get_db)
):
    resultado = await db.execute(
        select(Usuario).where(Usuario.email == dados.email)
    )

    usuario = resultado.scalar_one_or_none()

    if not usuario or not verificar_senha(
        dados.senha,
        usuario.senha
    ):
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos"
        )

    token = criar_token({
        "sub": usuario.email
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# =========================
# DEPÓSITO
# =========================

@app.post("/deposito")
async def deposito(
    dados: TransacaoCreate,
    email_usuario: str = Depends(verificar_token),
    db: AsyncSession = Depends(get_db)
):
    if dados.valor <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor do depósito deve ser positivo"
        )

    resultado = await db.execute(
        select(Conta).where(Conta.id == dados.conta_id)
    )

    conta = resultado.scalar_one_or_none()

    if not conta:
        raise HTTPException(
            status_code=404,
            detail="Conta não encontrada"
        )

    conta.saldo += dados.valor

    transacao = Transacao(
        tipo="depósito",
        valor=dados.valor,
        conta_id=conta.id
    )

    db.add(transacao)

    await db.commit()

    return {
        "mensagem": "Depósito realizado com sucesso",
        "saldo_atual": conta.saldo
    }


# =========================
# SAQUE
# =========================

@app.post("/saque")
async def saque(
    dados: TransacaoCreate,
    email_usuario: str = Depends(verificar_token),
    db: AsyncSession = Depends(get_db)
):
    if dados.valor <= 0:
        raise HTTPException(
            status_code=400,
            detail="O valor do saque deve ser positivo"
        )

    resultado = await db.execute(
        select(Conta).where(Conta.id == dados.conta_id)
    )

    conta = resultado.scalar_one_or_none()

    if not conta:
        raise HTTPException(
            status_code=404,
            detail="Conta não encontrada"
        )

    if conta.saldo < dados.valor:
        raise HTTPException(
            status_code=400,
            detail="Saldo insuficiente"
        )

    conta.saldo -= dados.valor

    transacao = Transacao(
        tipo="saque",
        valor=dados.valor,
        conta_id=conta.id
    )

    db.add(transacao)

    await db.commit()

    return {
        "mensagem": "Saque realizado com sucesso",
        "saldo_atual": conta.saldo
    }


# =========================
# EXTRATO
# =========================

@app.get("/contas/{conta_id}/extrato")
async def extrato(
    conta_id: int,
    email_usuario: str = Depends(verificar_token),
    db: AsyncSession = Depends(get_db)
):
    resultado = await db.execute(
        select(Conta).where(Conta.id == conta_id)
    )

    conta = resultado.scalar_one_or_none()

    if not conta:
        raise HTTPException(
            status_code=404,
            detail="Conta não encontrada"
        )

    resultado_transacoes = await db.execute(
        select(Transacao).where(
            Transacao.conta_id == conta_id
        )
    )

    transacoes = resultado_transacoes.scalars().all()

    return {
        "conta_id": conta.id,
        "saldo": conta.saldo,
        "transacoes": [
            {
                "id": transacao.id,
                "tipo": transacao.tipo,
                "valor": transacao.valor,
                "data": transacao.data
            }
            for transacao in transacoes
        ]
    }