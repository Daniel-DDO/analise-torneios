from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from app.db import engine
from app.models import AnaliseResultado, Fase

router = APIRouter(tags=["analise"])


@router.get("/fases/{fase_id}/analise")
def obter_analise(fase_id: str):
    """Retorna o resultado já processado (cache) - nunca recalcula na hora.
    Rápido mesmo com muitos acessos simultâneos, pois é só uma leitura no banco."""
    with Session(engine) as session:
        resultado = session.get(AnaliseResultado, fase_id)
        if resultado is None:
            raise HTTPException(
                status_code=404,
                detail="Análise ainda não calculada para essa fase. Chame POST /fases/{faseId}/sync primeiro.",
            )
        return {
            "faseId": fase_id,
            "calculadoEm": resultado.calculado_em,
            "numeroSimulacoes": resultado.n_simulacoes,
            **resultado.resultado,
        }


@router.get("/fases/{fase_id}/status")
def obter_status(fase_id: str):
    """Metadados simples: quando foi o último sync e se a fase já está encerrada.
    Útil pro front decidir se deve chamar /sync de novo (ex: cache muito antigo)."""
    with Session(engine) as session:
        fase = session.get(Fase, fase_id)
        if fase is None:
            raise HTTPException(status_code=404, detail="Fase ainda não sincronizada.")
        return {
            "faseId": fase.id,
            "encerrada": fase.encerrada,
            "ultimoSync": fase.ultimo_sync,
        }
