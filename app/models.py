from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON


class Fase(SQLModel, table=True):
    id: str = Field(primary_key=True)
    nome: str
    torneio_id: str
    torneio_nome: str
    tipo_torneio: str
    numero_rodadas: Optional[int] = None
    algoritmo_liga: Optional[str] = None
    # true quando todas as partidas foram realizadas -> nunca mais sincroniza nem recalcula
    encerrada: bool = False
    ultimo_sync: Optional[datetime] = None


class Participacao(SQLModel, table=True):
    # chave própria (id + fase_id), pra permitir limpar e recriar por fase sem conflitar
    id: str = Field(primary_key=True)
    fase_id: str = Field(index=True)
    jogador_clube_id: str
    nome_jogador: str
    nome_clube: str
    imagem_clube: Optional[str] = None
    pontos: int
    jogos: int
    vitorias: int
    empates: int
    derrotas: int
    gols_pro: int
    gols_contra: int
    saldo_gols: int
    # zonas são fixas ao longo da fase (confirmado): a mesma zona_nome sempre
    # corresponde ao mesmo grupo de posições fixas na tabela
    zona_nome: Optional[str] = None
    zona_cor: Optional[str] = None
    cartoes_amarelos: int = 0
    cartoes_vermelhos: int = 0


class Partida(SQLModel, table=True):
    id: str = Field(primary_key=True)
    fase_id: str = Field(index=True)
    rodada_id: Optional[str] = None
    numero_rodada: Optional[int] = None
    mandante_jogador_clube_id: Optional[str] = None
    visitante_jogador_clube_id: Optional[str] = None
    gols_mandante: Optional[int] = None
    gols_visitante: Optional[int] = None
    realizada: bool = False
    wo: bool = False


class AnaliseResultado(SQLModel, table=True):
    fase_id: str = Field(primary_key=True)
    resultado: Dict[str, Any] = Field(sa_column=Column(JSON))
    calculado_em: datetime
    n_simulacoes: int


class ParecerResultado(SQLModel, table=True):
    """Cache do 'parecer' (interpretação matemática + jogos decisivos) de uma
    fase. Guardado separado de AnaliseResultado porque é mais caro de calcular
    (roda simulações condicionais) e pode ser invalidado/recalculado de forma
    independente no futuro, se necessário."""
    fase_id: str = Field(primary_key=True)
    resultado: Dict[str, Any] = Field(sa_column=Column(JSON))
    calculado_em: datetime
