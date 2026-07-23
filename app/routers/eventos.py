from fastapi import APIRouter, BackgroundTasks
from app.sync_service import sincronizar_fase

router = APIRouter(tags=["eventos"])


@router.post("/fases/{fase_id}/eventos/partida-finalizada")
async def evento_partida_finalizada(fase_id: str, background_tasks: BackgroundTasks):
    """Chamado pelo FRONTEND (não pelo back Java) logo após o back Java confirmar
    o registro de uma partida daquela fase. Responde imediatamente e processa o
    recálculo em background - não é síncrono, o front não precisa esperar.

    Se a fase já estiver marcada como encerrada, o sync é ignorado automaticamente
    (nunca mais recalcula depois que todas as partidas foram realizadas).
    """
    background_tasks.add_task(sincronizar_fase, fase_id, False)
    return {"status": "recebido", "faseId": fase_id}
