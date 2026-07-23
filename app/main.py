from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# CORS liberado para qualquer origem: quem chama esse microsserviço é o
# FRONTEND diretamente (não o back Java), então não dá pra restringir a um
# único domínio sem quebrar localhost/produção/preview ao mesmo tempo.
# Como o serviço não usa cookies/sessão (sem autenticação própria), liberar
# geral aqui não expõe dados sensíveis por CSRF.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
