import httpx
from app.config import settings


async def buscar_fase(fase_id: str) -> dict:
    async with httpx.AsyncClient(base_url=settings.JAVA_BACKEND_URL, timeout=15) as client:
        resp = await client.get(f"/fase-torneio/{fase_id}")
        resp.raise_for_status()
        return resp.json()


async def buscar_participacoes(fase_id: str) -> list[dict]:
    async with httpx.AsyncClient(base_url=settings.JAVA_BACKEND_URL, timeout=15) as client:
        resp = await client.get(f"/participacao-fase/fase/{fase_id}")
        resp.raise_for_status()
        return resp.json()


async def buscar_todas_rodadas(fase_id: str) -> list[dict]:
    """O endpoint /rodada/fase/{faseId} é paginado (Spring Pageable).
    Itera todas as páginas até a última (last=True)."""
    rodadas: list[dict] = []
    page = 0
    async with httpx.AsyncClient(base_url=settings.JAVA_BACKEND_URL, timeout=15) as client:
        while True:
            resp = await client.get(
                f"/rodada/fase/{fase_id}",
                params={"page": page, "size": 100},
            )
            resp.raise_for_status()
            data = resp.json()
            rodadas.extend(data["content"])
            if data.get("last", True):
                break
            page += 1
    return rodadas
