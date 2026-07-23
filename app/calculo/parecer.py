from dataclasses import dataclass, replace
from app.models import Participacao
from app.calculo.monte_carlo import simular_temporada


@dataclass
class _TimeSnapshot:
    """Cópia leve e independente de uma Participacao, usada pra simular
    cenários hipotéticos (ex: 'e se esse jogo terminasse assim?') sem tocar
    nos objetos reais vindos do banco."""
    jogador_clube_id: str
    nome_jogador: str
    nome_clube: str
    pontos: int
    jogos: int
    vitorias: int
    empates: int
    derrotas: int
    gols_pro: int
    gols_contra: int
    saldo_gols: int
    zona_nome: str | None
    zona_cor: str | None
    cartoes_amarelos: int
    cartoes_vermelhos: int


def _snapshot(p: Participacao) -> _TimeSnapshot:
    return _TimeSnapshot(
        jogador_clube_id=p.jogador_clube_id,
        nome_jogador=p.nome_jogador,
        nome_clube=p.nome_clube,
        pontos=p.pontos,
        jogos=p.jogos,
        vitorias=p.vitorias,
        empates=p.empates,
        derrotas=p.derrotas,
        gols_pro=p.gols_pro,
        gols_contra=p.gols_contra,
        saldo_gols=p.saldo_gols,
        zona_nome=p.zona_nome,
        zona_cor=p.zona_cor,
        cartoes_amarelos=p.cartoes_amarelos,
        cartoes_vermelhos=p.cartoes_vermelhos,
    )


def _aplicar_resultado(
    snapshots: list[_TimeSnapshot], mandante_id: str, visitante_id: str, gm: int, gv: int
) -> list[_TimeSnapshot]:
    """Retorna uma NOVA lista de snapshots com o resultado (gm x gv) já
    aplicado ao confronto mandante x visitante. Não mexe na lista original."""
    novos = [replace(s) for s in snapshots]
    idx = {s.jogador_clube_id: i for i, s in enumerate(novos)}
    im, iv = idx[mandante_id], idx[visitante_id]
    m, v = novos[im], novos[iv]

    if gm > gv:
        m.pontos += 3
        m.vitorias += 1
        v.derrotas += 1
    elif gm < gv:
        v.pontos += 3
        v.vitorias += 1
        m.derrotas += 1
    else:
        m.pontos += 1
        v.pontos += 1
        m.empates += 1
        v.empates += 1

    m.jogos += 1
    v.jogos += 1
    m.gols_pro += gm
    m.gols_contra += gv
    m.saldo_gols += gm - gv
    v.gols_pro += gv
    v.gols_contra += gm
    v.saldo_gols += gv - gm

    return novos


# --- Situações matemáticas (melhor caso / pior caso) ---

def _pontos_minimos_e_maximos(
    participacoes: list[Participacao], partidas_restantes: list[dict]
) -> dict[str, dict[str, int]]:
    """Pra cada time: quantos jogos ainda tem, e quantos pontos consegue no
    MÍNIMO (perde tudo -> mantém os pontos atuais) e no MÁXIMO (vence tudo)."""
    jogos_restantes_por_time: dict[str, int] = {p.jogador_clube_id: 0 for p in participacoes}
    for jogo in partidas_restantes:
        if jogo["mandante_id"] in jogos_restantes_por_time:
            jogos_restantes_por_time[jogo["mandante_id"]] += 1
        if jogo["visitante_id"] in jogos_restantes_por_time:
            jogos_restantes_por_time[jogo["visitante_id"]] += 1

    extremos: dict[str, dict[str, int]] = {}
    for p in participacoes:
        restantes = jogos_restantes_por_time.get(p.jogador_clube_id, 0)
        extremos[p.jogador_clube_id] = {
            "minimo": p.pontos,                    # pior caso: perde tudo, não soma nada
            "maximo": p.pontos + restantes * 3,     # melhor caso: vence tudo
            "jogosRestantes": restantes,
        }
    return extremos


def calcular_situacoes_matematicas(
    participacoes: list[Participacao],
    partidas_restantes: list[dict],
    zonas_ranges: dict[str, tuple[int, int]],
    zona_rebaixamento: str | None,
) -> list[dict]:
    """Gera o veredito matemático de cada time: campeão/eliminado do título,
    garantido/eliminado de uma zona, matematicamente rebaixado, etc.

    IMPORTANTE sobre a garantia matemática: os limites usados aqui (contar
    quantos adversários PODERIAM ultrapassar o time, no pior caso) são
    limites SEGUROS - nunca afirmam uma garantia que não existe de fato.
    Podem, em casos raríssimos de calendários muito entrelaçados, deixar de
    detectar uma eliminação/classificação que só um algoritmo de fluxo
    máximo (bem mais caro) capturaria - mas nunca erram para o lado
    otimista. Ou seja: se o sistema diz "matematicamente rebaixado", é
    porque é impossível escapar, sem exceções.
    """
    extremos = _pontos_minimos_e_maximos(participacoes, partidas_restantes)
    situacoes: list[dict] = []

    for p in participacoes:
        tid = p.jogador_clube_id
        meu_min = extremos[tid]["minimo"]
        meu_max = extremos[tid]["maximo"]

        # 1) Título: elimino se existe alguém cujo piso (pontos atuais) já
        # supera meu teto (máximo que ainda posso alcançar).
        eliminado_titulo = any(
            extremos[o.jogador_clube_id]["minimo"] > meu_max
            for o in participacoes if o.jogador_clube_id != tid
        )
        # Campeão matemático: meu piso supera o teto de TODOS os outros.
        campeao_matematico = all(
            meu_min > extremos[o.jogador_clube_id]["maximo"]
            for o in participacoes if o.jogador_clube_id != tid
        )

        status = None
        mensagem = None

        if campeao_matematico:
            status = "CAMPEAO_MATEMATICO"
            mensagem = f"{p.nome_jogador} ({p.nome_clube}) já garantiu o título, independentemente dos resultados restantes."
        elif zona_rebaixamento and p.zona_nome == zona_rebaixamento:
            baixo, _alto = zonas_ranges.get(zona_rebaixamento, (None, None))
            # Melhor posição possível: 1 + quantos adversários JÁ garantem
            # (piso deles > meu teto) terminar acima de mim, o que é uma
            # afirmação sempre verdadeira (não depende de suposição).
            garantidos_acima = sum(
                1 for o in participacoes
                if o.jogador_clube_id != tid and extremos[o.jogador_clube_id]["minimo"] > meu_max
            )
            melhor_posicao_possivel = 1 + garantidos_acima
            if baixo is not None and melhor_posicao_possivel >= baixo:
                status = "REBAIXAMENTO_MATEMATICO"
                mensagem = f"{p.nome_jogador} ({p.nome_clube}) está matematicamente rebaixado - não há mais como escapar da zona, independentemente dos resultados restantes."

        if status is None and eliminado_titulo:
            status = "ELIMINADO_DO_TITULO"
            mensagem = f"{p.nome_jogador} ({p.nome_clube}) não pode mais ser campeão desta fase, mesmo vencendo todos os jogos restantes."

        if status is None:
            # Verifica se já garantiu permanecer numa zona específica
            # (ex: classificação), usando o limite seguro de "pior posição
            # possível": 1 + quantos adversários PODERIAM (teto deles > meu
            # piso) terminar acima de mim.
            # Nunca aplicamos essa checagem à zona de REBAIXAMENTO: pra ela,
            # a condição seria trivialmente verdadeira (é a última zona -
            # "garantir" terminar nela ou acima não significa nada bom). O
            # único status relevante pra quem está na zona de rebaixamento é
            # REBAIXAMENTO_MATEMATICO (já tratado acima) ou EM_DISPUTA.
            eh_zona_rebaixamento = zona_rebaixamento is not None and p.zona_nome == zona_rebaixamento
            if p.zona_nome and p.zona_nome in zonas_ranges and not eh_zona_rebaixamento:
                _baixo, alto = zonas_ranges[p.zona_nome]
                poderiam_ultrapassar = sum(
                    1 for o in participacoes
                    if o.jogador_clube_id != tid and extremos[o.jogador_clube_id]["maximo"] > meu_min
                )
                pior_posicao_possivel = 1 + poderiam_ultrapassar
                if pior_posicao_possivel <= alto:
                    status = "ZONA_GARANTIDA"
                    mensagem = f"{p.nome_jogador} ({p.nome_clube}) já garantiu permanecer em '{p.zona_nome}', independentemente dos resultados restantes."

        if status is None:
            status = "EM_DISPUTA"
            mensagem = f"{p.nome_jogador} ({p.nome_clube}) ainda depende de resultados para definir sua situação nesta fase."

        situacoes.append({
            "jogadorClubeId": tid,
            "nomeJogador": p.nome_jogador,
            "nomeClube": p.nome_clube,
            "status": status,
            "mensagem": mensagem,
            "pontosMinimoGarantido": meu_min,
            "pontosMaximoPossivel": meu_max,
            "jogosRestantes": extremos[tid]["jogosRestantes"],
        })

    return situacoes


# --- Jogos decisivos (simulação condicional) ---

def calcular_jogos_decisivos(
    participacoes: list[Participacao],
    partidas_da_proxima_rodada: list[dict],
    todas_partidas_restantes: list[dict],
    zonas_ranges: dict[str, tuple[int, int]],
    zona_rebaixamento: str | None,
    n_simulacoes: int = 3000,
    limiar_impacto: float = 0.15,
) -> list[dict]:
    """Para cada jogo da PRÓXIMA rodada (limitado de propósito, pra manter o
    cálculo rápido - jogos mais distantes têm relevância prática menor e
    custo de simulação maior), roda 3 simulações condicionais (vitória
    mandante / empate / vitória visitante) e mede o quanto isso muda a
    probabilidade de cada um dos dois times envolvidos ficar na zona de
    rebaixamento ou no título. Jogos cuja variação passa do limiar são
    marcados como decisivos."""
    if not partidas_da_proxima_rodada:
        return []

    snapshots = [_snapshot(p) for p in participacoes]
    decisivos: list[dict] = []

    for jogo in partidas_da_proxima_rodada:
        mandante_id = jogo["mandante_id"]
        visitante_id = jogo["visitante_id"]

        # partidas restantes SEM esse confronto (ele será fixado)
        restantes_sem_este = [
            j for j in todas_partidas_restantes
            if not (j["mandante_id"] == mandante_id and j["visitante_id"] == visitante_id)
        ]

        cenarios = {
            "vitoriaMandante": _aplicar_resultado(snapshots, mandante_id, visitante_id, 1, 0),
            "empate": _aplicar_resultado(snapshots, mandante_id, visitante_id, 0, 0),
            "vitoriaVisitante": _aplicar_resultado(snapshots, mandante_id, visitante_id, 0, 1),
        }

        probs_por_cenario: dict[str, dict] = {}
        for nome_cenario, snap in cenarios.items():
            resultado = simular_temporada(
                participacoes=snap,  # duck-typing: mesmos atributos de Participacao
                partidas_restantes=restantes_sem_este,
                n_simulacoes=n_simulacoes,
            )
            probs_por_cenario[nome_cenario] = resultado

        maior_impacto = 0.0
        detalhes_times = []

        def _prob_rebaixamento(resultado_sim: dict, tid: str) -> float | None:
            if not zona_rebaixamento:
                return None
            dados = resultado_sim.get(tid)
            if not dados:
                return None
            baixo, alto = zonas_ranges.get(zona_rebaixamento, (None, None))
            if baixo is None:
                return None
            return sum(
                prob for pos, prob in dados["distribuicaoPosicoes"].items()
                if baixo <= pos <= alto
            )

        def _prob_titulo(resultado_sim: dict, tid: str) -> float | None:
            dados = resultado_sim.get(tid)
            return dados["probTitulo"] if dados else None

        def _prob_zona_propria(resultado_sim: dict, tid: str, zona_nome: str | None) -> float | None:
            if not zona_nome or zona_nome not in zonas_ranges:
                return None
            dados = resultado_sim.get(tid)
            if not dados:
                return None
            baixo, alto = zonas_ranges[zona_nome]
            return sum(
                prob for pos, prob in dados["distribuicaoPosicoes"].items()
                if baixo <= pos <= alto
            )

        for tid in (mandante_id, visitante_id):
            time_info = next((p for p in participacoes if p.jogador_clube_id == tid), None)
            if time_info is None:
                continue

            resultado_vitoria = probs_por_cenario["vitoriaMandante"] if tid == mandante_id else probs_por_cenario["vitoriaVisitante"]
            resultado_derrota = probs_por_cenario["vitoriaVisitante"] if tid == mandante_id else probs_por_cenario["vitoriaMandante"]
            resultado_empate = probs_por_cenario["empate"]

            # Avalia as métricas relevantes pra esse time (rebaixamento, título,
            # zona própria) e usa a que tiver MAIOR variação - é a que
            # realmente importa pra esse time nesse confronto específico.
            candidatas: list[tuple[str, float, float, float]] = []
            for nome_metrica, extrator in (
                ("probRebaixamento", _prob_rebaixamento),
                ("probTitulo", _prob_titulo),
                ("probZona", lambda r, t: _prob_zona_propria(r, t, time_info.zona_nome)),
            ):
                pv = extrator(resultado_vitoria, tid)
                pe = extrator(resultado_empate, tid)
                pd = extrator(resultado_derrota, tid)
                if pv is None or pe is None or pd is None:
                    continue
                candidatas.append((nome_metrica, pv, pe, pd))

            if not candidatas:
                continue

            nome_metrica, p_vitoria, p_empate, p_derrota = max(
                candidatas, key=lambda c: max(c[1], c[2], c[3]) - min(c[1], c[2], c[3])
            )
            impacto = max(p_vitoria, p_empate, p_derrota) - min(p_vitoria, p_empate, p_derrota)
            maior_impacto = max(maior_impacto, impacto)

            detalhes_times.append({
                "jogadorClubeId": tid,
                "nomeJogador": time_info.nome_jogador,
                "nomeClube": time_info.nome_clube,
                "metrica": nome_metrica,
                "probSeVitoria": round(p_vitoria, 4),
                "probSeEmpate": round(p_empate, 4),
                "probSeDerrota": round(p_derrota, 4),
                "impacto": round(impacto, 4),
            })

        if maior_impacto >= limiar_impacto:
            mandante_info = next((p for p in participacoes if p.jogador_clube_id == mandante_id), None)
            visitante_info = next((p for p in participacoes if p.jogador_clube_id == visitante_id), None)
            decisivos.append({
                "partidaId": jogo.get("partida_id"),
                "numeroRodada": jogo.get("numero_rodada"),
                "mandante": mandante_info.nome_clube if mandante_info else None,
                "visitante": visitante_info.nome_clube if visitante_info else None,
                "impacto": "ALTO" if maior_impacto >= 0.35 else "MEDIO",
                "variacaoMaxima": round(maior_impacto, 4),
                "times": detalhes_times,
            })

    decisivos.sort(key=lambda d: d["variacaoMaxima"], reverse=True)
    return decisivos
