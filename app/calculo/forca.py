from app.models import Participacao


def calcular_forcas(participacoes: list[Participacao]) -> dict[str, float]:
    """Score simples de força por jogador/clube, baseado no desempenho até agora.
    0.3 de baseline evita força zero/negativa para quem tem poucos jogos ou começou mal.
    """
    forcas: dict[str, float] = {}
    for p in participacoes:
        jogos = max(p.jogos, 1)
        aproveitamento = p.pontos / (jogos * 3)
        media_gols_pro = p.gols_pro / jogos
        media_gols_contra = p.gols_contra / jogos
        saldo_medio = media_gols_pro - media_gols_contra

        score = 0.3 + aproveitamento * 0.6 + saldo_medio * 0.1
        forcas[p.jogador_clube_id] = max(score, 0.05)
    return forcas
