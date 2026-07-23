from fastapi import FastAPI
from app.db import criar_tabelas
from app.routers import sync, eventos, analise

app = FastAPI(
    title="Análise de Torneios - Microsserviço de Probabilidades",
    description=(
        "Calcula favorito ao título, chances de classificação/rebaixamento, "
        "posição final projetada e simulações Monte Carlo. Mantém cache próprio "
        "e só recalcula quando avisado (eventos) ou via sync manual."
    ),
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    criar_tabelas()


app.include_router(sync.router)
app.include_router(eventos.router)
app.include_router(analise.router)


@app.get("/")
def health():
    return {"status": "ok"}
