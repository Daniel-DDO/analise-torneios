from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from app.db import engine
from app.models import AnaliseResultado, Fase, ParecerResultado

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


@router.get("/fases/{fase_id}/parecer")
def obter_parecer(fase_id: str):
    """Retorna o 'parecer' da fase: situações matemáticas de cada time
    (campeão matemático, eliminado, rebaixamento matemático, zona garantida
    etc.) e os jogos decisivos da próxima rodada, com o impacto de cada
    resultado possível. Assim como /analise, é sempre cache - nunca
    recalcula na hora (o cálculo é mais pesado, roda simulações
    condicionais, então acontece junto do /sync ou do evento de partida
    finalizada, em background)."""
    with Session(engine) as session:
        parecer = session.get(ParecerResultado, fase_id)
        if parecer is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Parecer ainda não calculado para essa fase. Chame POST "
                    "/fases/{faseId}/sync primeiro (ou aguarde: fases encerradas "
                    "ou sem jogos restantes não geram parecer, pois não há mais "
                    "nada a decidir)."
                ),
            )
        return {
            "faseId": fase_id,
            "calculadoEm": parecer.calculado_em,
            **parecer.resultado,
        }
