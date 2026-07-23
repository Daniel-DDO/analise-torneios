MEDIA_LIGA_GOLS = 1.4
FATOR_CASA = 1.15


def gols_esperados(forca_mandante: float, forca_visitante: float) -> tuple[float, float]:
    """Retorna (lambda_mandante, lambda_visitante) para uso em Poisson.
    Times mais fortes geram lambda maior; fator_casa dá vantagem ao mandante."""
    lambda_mandante = MEDIA_LIGA_GOLS * FATOR_CASA * (forca_mandante / max(forca_visitante, 0.01))
    lambda_visitante = MEDIA_LIGA_GOLS * (forca_visitante / max(forca_mandante, 0.01))
    return max(lambda_mandante, 0.1), max(lambda_visitante, 0.1)
