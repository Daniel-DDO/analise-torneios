from fastapi import APIRouter
from app.sync_service import sincronizar_fase

router = APIRouter(tags=["sync"])


@router.post("/fases/{fase_id}/sync")
async def sync_manual(fase_id: str, forcar: bool = False):
    """Sync completo da fase: busca fase + participações + rodadas/partidas no
    back Java, popula o banco próprio e recalcula as probabilidades.

    Chame isso quando:
    - o usuário entra na tela de análise de uma fase pela primeira vez
    - você quer forçar um recálculo manual (forcar=true ignora o flag 'encerrada')
    """
    return await sincronizar_fase(fase_id, forcar=forcar)
