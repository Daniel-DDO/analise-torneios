from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models import Fase, Participacao, Partida, AnaliseResultado, ParecerResultado
from app.calculo.monte_carlo import simular_temporada
from app.calculo.parecer import calcular_situacoes_matematicas, calcular_jogos_decisivos
from app.config import settings


def _mapear_zonas_por_posicao(participacoes: list[Participacao]) -> dict[str, tuple[int, int]]:
    """As zonas são fixas por posição (confirmado pelo usuário): a mesma zona_nome
    sempre corresponde ao mesmo grupo de posições. Como não existe endpoint de
    configuração de zonas, inferimos o range de posições de cada zona a partir da
    ordenação ATUAL da tabela (que já vem ordenada por posicao no /participacao-fase).
    Ex: se times nas posições 1-4 tem zona "Libertadores", o range fica (1, 4).
    """
    ordenados = sorted(participacoes, key=lambda p: p.pontos, reverse=True)
    # nota: aqui usamos a ordem de posicao vinda do back (já teve o desempate certo aplicado
    # por ele); recomputamos o range de cada zona olhando a sequência de zona_nome.
    ranges: dict[str, tuple[int, int]] = {}
    for i, p in enumerate(ordenados, start=1):
        zona = p.zona_nome
        if zona is None:
            continue
        if zona not in ranges:
            ranges[zona] = (i, i)
        else:
            ranges[zona] = (ranges[zona][0], i)
    return ranges


async def recalcular_fase(fase_id: str, session: Session) -> None:
    fase = session.get(Fase, fase_id)
    if fase is None:
        return

    participacoes = session.exec(
        select(Participacao).where(Participacao.fase_id == fase_id)
    ).all()
    if not participacoes:
        return

    partidas = session.exec(
        select(Partida).where(Partida.fase_id == fase_id)
    ).all()

    partidas_restantes = [
        {
            "partida_id": p.id,
            "numero_rodada": p.numero_rodada,
            "mandante_id": p.mandante_jogador_clube_id,
            "visitante_id": p.visitante_jogador_clube_id,
        }
        for p in partidas
        if not p.realizada and not p.wo
        and p.mandante_jogador_clube_id and p.visitante_jogador_clube_id
    ]

    n_sim = settings.N_SIMULACOES_MONTE_CARLO
    if fase.encerrada or not partidas_restantes:
        # fase acabou (ou não há mais jogos): não simula, resultado é a tabela final
        n_sim = 1

    resultado_por_time = simular_temporada(
        participacoes=participacoes,
        partidas_restantes=partidas_restantes,
        n_simulacoes=n_sim,
    )

    zonas_ranges = _mapear_zonas_por_posicao(participacoes)
    # heurística: a zona com o range de posições mais alto (maiores números) é rebaixamento,
    # SE o nome sugerir isso. Caso não dê pra inferir com segurança, deixamos null e o front
    # decide como exibir - ajustar aqui se você tiver uma convenção de nome fixa (ex: sempre
    # contém "Rebaixamento").
    zona_rebaixamento = next(
        (nome for nome in zonas_ranges if "rebaix" in nome.lower()), None
    )

    for tid, dados in resultado_por_time.items():
        zona = dados["zonaNome"]
        if zona and zona in zonas_ranges:
            baixo, alto = zonas_ranges[zona]
            dados["probZona"] = round(
                sum(
                    prob for pos, prob in dados["distribuicaoPosicoes"].items()
                    if baixo <= pos <= alto
                ),
                4,
            )
        else:
            dados["probZona"] = None

        if zona_rebaixamento:
            baixo, alto = zonas_ranges[zona_rebaixamento]
            dados["probRebaixamento"] = round(
                sum(
                    prob for pos, prob in dados["distribuicaoPosicoes"].items()
                    if baixo <= pos <= alto
                ),
                4,
            )

    favorito_id = max(resultado_por_time.items(), key=lambda kv: kv[1]["probTitulo"])[0]
    nomes_por_id = {p.jogador_clube_id: p.nome_jogador for p in participacoes}
    clubes_por_id = {p.jogador_clube_id: p.nome_clube for p in participacoes}

    payload = {
        "faseEncerrada": fase.encerrada,
        "favorito": {
            "jogadorClubeId": favorito_id,
            "nomeJogador": nomes_por_id.get(favorito_id),
            "nomeClube": clubes_por_id.get(favorito_id),
            "probTitulo": resultado_por_time[favorito_id]["probTitulo"],
        },
        "times": [
            {
                "jogadorClubeId": tid,
                "nomeJogador": nomes_por_id.get(tid),
                "nomeClube": clubes_por_id.get(tid),
                **dados,
            }
            for tid, dados in resultado_por_time.items()
        ],
    }

    existente = session.get(AnaliseResultado, fase_id)
    if existente:
        existente.resultado = payload
        existente.calculado_em = datetime.now(timezone.utc)
        existente.n_simulacoes = n_sim
        session.add(existente)
    else:
        session.add(AnaliseResultado(
            fase_id=fase_id,
            resultado=payload,
            calculado_em=datetime.now(timezone.utc),
            n_simulacoes=n_sim,
        ))
    session.commit()

    # --- Parecer (situações matemáticas + jogos decisivos) ---
    # Só faz sentido enquanto a fase está em andamento e tem jogo restante;
    # se encerrou, não há mais nada "decisivo" pra calcular.
    if not fase.encerrada and partidas_restantes:
        situacoes = calcular_situacoes_matematicas(
            participacoes=participacoes,
            partidas_restantes=partidas_restantes,
            zonas_ranges=zonas_ranges,
            zona_rebaixamento=zona_rebaixamento,
        )

        menor_rodada_pendente = min(
            (j["numero_rodada"] for j in partidas_restantes if j["numero_rodada"] is not None),
            default=None,
        )
        partidas_proxima_rodada = [
            j for j in partidas_restantes if j["numero_rodada"] == menor_rodada_pendente
        ] if menor_rodada_pendente is not None else []

        jogos_decisivos = calcular_jogos_decisivos(
            participacoes=participacoes,
            partidas_da_proxima_rodada=partidas_proxima_rodada,
            todas_partidas_restantes=partidas_restantes,
            zonas_ranges=zonas_ranges,
            zona_rebaixamento=zona_rebaixamento,
        )

        parecer_payload = {
            "proximaRodada": menor_rodada_pendente,
            "situacoes": situacoes,
            "jogosDecisivos": jogos_decisivos,
        }

        parecer_existente = session.get(ParecerResultado, fase_id)
        if parecer_existente:
            parecer_existente.resultado = parecer_payload
            parecer_existente.calculado_em = datetime.now(timezone.utc)
            session.add(parecer_existente)
        else:
            session.add(ParecerResultado(
                fase_id=fase_id,
                resultado=parecer_payload,
                calculado_em=datetime.now(timezone.utc),
            ))
        session.commit()
