from datetime import datetime, timezone
from sqlmodel import Session, select
from app.db import engine
from app.models import Fase, Participacao, Partida
from app.client_java import buscar_fase, buscar_participacoes, buscar_todas_rodadas
from app.calculo.pipeline import recalcular_fase


async def sincronizar_fase(fase_id: str, forcar: bool = False) -> dict:
    """Busca os dados atuais da fase no back Java, atualiza o banco próprio
    do microsserviço e recalcula as probabilidades.

    Se a fase já estiver marcada como encerrada (todas as partidas realizadas),
    não busca nada de novo nem recalcula - a menos que forcar=True."""
    with Session(engine) as session:
        fase_existente = session.get(Fase, fase_id)
        if fase_existente is not None and fase_existente.encerrada and not forcar:
            return {"status": "ignorado", "motivo": "fase já encerrada", "faseId": fase_id}

        fase_dto = await buscar_fase(fase_id)
        participacoes_dto = await buscar_participacoes(fase_id)
        rodadas_dto = await buscar_todas_rodadas(fase_id)

        fase = session.get(Fase, fase_id)
        if fase is None:
            fase = Fase(id=fase_id, nome="", torneio_id="", torneio_nome="", tipo_torneio="")

        fase.nome = fase_dto["nome"]
        fase.torneio_id = fase_dto["torneioId"]
        fase.torneio_nome = fase_dto["torneioNome"]
        fase.tipo_torneio = fase_dto["tipoTorneio"]
        fase.numero_rodadas = fase_dto.get("numeroRodadas")
        fase.algoritmo_liga = fase_dto.get("algoritmoLiga")
        session.add(fase)
        session.commit()

        # limpa e recria participações (mais simples e seguro que diffar campo a campo)
        antigas_participacoes = session.exec(
            select(Participacao).where(Participacao.fase_id == fase_id)
        ).all()
        for p in antigas_participacoes:
            session.delete(p)
        session.commit()

        for p in participacoes_dto:
            session.add(Participacao(
                id=p["id"],
                fase_id=fase_id,
                jogador_clube_id=p["jogadorClubeId"],
                nome_jogador=p["nomeJogador"],
                nome_clube=p["nomeClube"],
                imagem_clube=p.get("imagemClube"),
                pontos=p["pontos"],
                jogos=p["jogos"],
                vitorias=p["vitorias"],
                empates=p["empates"],
                derrotas=p["derrotas"],
                gols_pro=p["golsPro"],
                gols_contra=p["golsContra"],
                saldo_gols=p["saldoGols"],
                zona_nome=p.get("zonaNome"),
                zona_cor=p.get("zonaCor"),
            ))
        session.commit()

        # limpa e recria partidas
        antigas_partidas = session.exec(
            select(Partida).where(Partida.fase_id == fase_id)
        ).all()
        for p in antigas_partidas:
            session.delete(p)
        session.commit()

        todas_partidas_dto = [
            partida for rodada in rodadas_dto for partida in rodada.get("partidas", [])
        ]
        for pt in todas_partidas_dto:
            mandante = pt.get("mandante")
            visitante = pt.get("visitante")
            session.add(Partida(
                id=pt["id"],
                fase_id=fase_id,
                rodada_id=pt.get("rodadaId"),
                numero_rodada=pt.get("numeroRodada"),
                mandante_jogador_clube_id=mandante["id"] if mandante else None,
                visitante_jogador_clube_id=visitante["id"] if visitante else None,
                gols_mandante=pt.get("golsMandante"),
                gols_visitante=pt.get("golsVisitante"),
                realizada=pt["realizada"],
                wo=pt["wo"],
            ))
        session.commit()

        # fase encerrada = todas as partidas cadastradas já foram realizadas
        encerrada = len(todas_partidas_dto) > 0 and all(
            pt["realizada"] for pt in todas_partidas_dto
        )
        fase = session.get(Fase, fase_id)
        fase.encerrada = encerrada
        fase.ultimo_sync = datetime.now(timezone.utc)
        session.add(fase)
        session.commit()

        await recalcular_fase(fase_id, session)

        return {
            "status": "sincronizado",
            "faseId": fase_id,
            "encerrada": encerrada,
            "totalPartidas": len(todas_partidas_dto),
        }
