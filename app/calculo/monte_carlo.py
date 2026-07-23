import numpy as np
from app.models import Participacao
from app.calculo.forca import calcular_forcas
from app.calculo.probabilidades import gols_esperados


def simular_temporada(
    participacoes: list[Participacao],
    partidas_restantes: list[dict],  # cada item: {mandante_id, visitante_id}
    n_simulacoes: int = 10_000,
    seed: int = 42,
) -> dict:
    """Simula o restante do campeonato N vezes e agrega estatísticas por time.

    Critério de desempate replicado do back Java (LinhaClassificacaoDTO):
    pontos desc, saldo desc, vitorias desc, gols_pro desc, gols_contra asc,
    amarelos asc, vermelhos asc. Confronto direto (último critério do Java)
    não é simulado aqui - ver observação no README.
    """
    rng = np.random.default_rng(seed)
    forcas = calcular_forcas(participacoes)

    ids = [p.jogador_clube_id for p in participacoes]
    idx = {tid: i for i, tid in enumerate(ids)}
    n_times = len(ids)

    pontos = np.tile(np.array([p.pontos for p in participacoes], dtype=float), (n_simulacoes, 1))
    saldo = np.tile(np.array([p.saldo_gols for p in participacoes], dtype=float), (n_simulacoes, 1))
    vitorias = np.tile(np.array([p.vitorias for p in participacoes], dtype=float), (n_simulacoes, 1))
    gols_pro = np.tile(np.array([p.gols_pro for p in participacoes], dtype=float), (n_simulacoes, 1))
    gols_contra = np.tile(np.array([p.gols_contra for p in participacoes], dtype=float), (n_simulacoes, 1))
    amarelos = np.tile(np.array([p.cartoes_amarelos for p in participacoes], dtype=float), (n_simulacoes, 1))
    vermelhos = np.tile(np.array([p.cartoes_vermelhos for p in participacoes], dtype=float), (n_simulacoes, 1))

    for jogo in partidas_restantes:
        i_m = idx.get(jogo["mandante_id"])
        i_v = idx.get(jogo["visitante_id"])
        if i_m is None or i_v is None:
            continue  # segurança: ignora partida com time fora da fase (não deveria acontecer)

        lambda_m, lambda_v = gols_esperados(forcas[jogo["mandante_id"]], forcas[jogo["visitante_id"]])
        gm = rng.poisson(lambda_m, size=n_simulacoes)
        gv = rng.poisson(lambda_v, size=n_simulacoes)

        vitoria_m = gm > gv
        vitoria_v = gv > gm
        empate = gm == gv

        pontos[:, i_m] += np.where(vitoria_m, 3, np.where(empate, 1, 0))
        pontos[:, i_v] += np.where(vitoria_v, 3, np.where(empate, 1, 0))
        vitorias[:, i_m] += vitoria_m
        vitorias[:, i_v] += vitoria_v
        saldo[:, i_m] += gm - gv
        saldo[:, i_v] += gv - gm
        gols_pro[:, i_m] += gm
        gols_pro[:, i_v] += gv
        gols_contra[:, i_m] += gv
        gols_contra[:, i_v] += gm
        # amarelos/vermelhos: sem previsão futura confiável, mantidos como estão

    # lexsort ordena pela última chave como critério PRIMÁRIO -> ordem invertida da prioridade
    ordenacao = np.lexsort(
        (
            vermelhos,      # menor melhor -> asc (última prioridade real, mas aqui é a mais "fina")
            amarelos,       # menor melhor -> asc
            -gols_contra,   # menor melhor -> negativo para ordenar desc-do-negativo = asc
            -gols_pro,      # maior melhor -> desc
            -vitorias,      # maior melhor -> desc
            -saldo,         # maior melhor -> desc
            -pontos,        # maior melhor -> desc (critério mais importante, aplicado por último no lexsort)
        ),
        axis=1,
    )

    posicoes = np.empty_like(ordenacao)
    linhas = np.arange(n_simulacoes)[:, None]
    for col in range(n_times):
        posicoes[linhas[:, 0], ordenacao[:, col]] = col + 1

    zonas_por_time = {p.jogador_clube_id: p.zona_nome for p in participacoes}
    cores_por_zona = {p.jogador_clube_id: p.zona_cor for p in participacoes}

    resultado: dict[str, dict] = {}
    for tid in ids:
        i = idx[tid]
        pos_time = posicoes[:, i]
        resultado[tid] = {
            "posicaoMedia": round(float(pos_time.mean()), 2),
            "posicaoMediana": float(np.median(pos_time)),
            "probTitulo": round(float((pos_time == 1).mean()), 4),
            "probRebaixamento": None,  # calculado no pipeline, que sabe quais zonas são rebaixamento
            "zonaNome": zonas_por_time.get(tid),
            "zonaCor": cores_por_zona.get(tid),
            "distribuicaoPosicoes": {
                int(p): round(float((pos_time == p).mean()), 4) for p in range(1, n_times + 1)
            },
        }
    return resultado
