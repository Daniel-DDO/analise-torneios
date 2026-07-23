from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def criar_tabelas():
    """Cria as tabelas automaticamente se não existirem. Chamado no startup do app.
    Não é migração (não altera colunas existentes) - só cria o que não existe.
    Se precisar alterar schema depois de já ter dados em produção, aí sim
    vale introduzir Alembic. Pra começar, isso é suficiente."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
