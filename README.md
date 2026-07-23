# analise-torneios

Microsserviço em FastAPI que calcula probabilidades e projeções (favorito ao
título, classificação, rebaixamento, posição final, simulação Monte Carlo)
para as fases do `torneios-ddo`. Mantém banco próprio e só recalcula quando
avisado — nunca consulta o back Java repetidamente.

## 1. Pré-requisitos

- Python 3.11+ instalado (`python --version` pra conferir)
- Docker Desktop instalado (só se você quiser usar Postgres via `docker-compose`;
  se preferir, dá pra testar tudo com SQLite sem Docker nenhum)

## 2. Rodando pela primeira vez (SQLite — mais simples, sem Docker)

Abra o terminal do VS Code (Ctrl+` ou Terminal > Novo Terminal) dentro da
pasta `analise-torneios` e rode, em sequência:

```bash
# 1. cria um ambiente virtual isolado (evita bagunçar pacotes globais do seu PC)
python -m venv venv

# 2. ativa o ambiente virtual
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (cmd):
venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate

# 3. instala as dependências
pip install -r requirements.txt

# 4. cria o .env a partir do exemplo
# Windows (PowerShell):
Copy-Item .env.example .env
# Linux/Mac:
cp .env.example .env
```

Agora abra o `.env` que acabou de ser criado e, pra começar simples sem
Postgres, **troque a linha `DATABASE_URL`** para usar SQLite:

```env
DATABASE_URL=sqlite:///./analise.db
```

(Deixe `JAVA_BACKEND_URL` apontando pro endereço real do seu back Java, ex:
`http://localhost:8080`.)

Por fim, suba o servidor:

```bash
uvicorn app.main:app --reload --port 8000
```

Se aparecer algo como `Uvicorn running on http://127.0.0.1:8000`, deu certo.
As tabelas do banco (`analise.db`, um arquivo SQLite) são **criadas
automaticamente** no startup — você não precisa rodar nenhum comando de
migração nem criar entidade manualmente.

Acesse `http://localhost:8000/docs` no navegador — o Swagger já vem pronto
com todos os endpoints pra você testar clicando, sem precisar de Postman.

## 3. Rodando com Postgres (via Docker, opcional)

Se preferir Postgres em vez de SQLite (recomendado se for usar em produção):

```bash
docker compose up -d
```

Isso sobe um Postgres na porta `5433` (local) com usuário `analise`, senha
`analise123`, banco `analise_torneios` — já bate com o `DATABASE_URL` padrão
do `.env.example`. Nesse caso, **não precisa** trocar pra SQLite, é só manter
a linha `DATABASE_URL=postgresql+psycopg2://...` como está.

Depois, os mesmos passos 3-6 do item acima (venv, pip install, uvicorn).

Pra derrubar o Postgres depois: `docker compose down` (ou `docker compose down -v`
pra apagar os dados também).

## 4. Testando o fluxo completo

Com o servidor rodando e o back Java também rodando (ex: `localhost:8080`):

```bash
# sync inicial de uma fase (troque pelo faseId real)
curl -X POST http://localhost:8000/fases/8d1c23d1-3744-476e-b736-5f62a8cd1d93/sync

# consultar a análise já processada
curl http://localhost:8000/fases/8d1c23d1-3744-476e-b736-5f62a8cd1d93/analise

# simular o evento de "partida finalizada" (é isso que o FRONTEND deve chamar
# depois que o back Java confirmar o registro de uma partida)
curl -X POST http://localhost:8000/fases/8d1c23d1-3744-476e-b736-5f62a8cd1d93/eventos/partida-finalizada
```

## 5. Integração com o frontend

No fluxo de registro de partida do seu app React/TypeScript, depois da
chamada normal pro back Java ser confirmada com sucesso, adicione (sem
esperar a resposta travar a UI):

```typescript
async function registrarPartida(partidaId: string, faseId: string, dados: any) {
  await apiJava.post(`/partida/${partidaId}/resultado`, dados); // fluxo normal, já existente

  // dispara em paralelo, sem bloquear a UI - não precisa de try/catch
  // agressivo aqui, se falhar o próximo /sync manual ou o polling de
  // segurança corrige depois
  fetch(`http://localhost:8000/fases/${faseId}/eventos/partida-finalizada`, {
    method: "POST",
  }).catch(() => {});
}
```

## 6. Estrutura do projeto

```
analise-torneios/
├── app/
│   ├── main.py              # FastAPI app, registra as rotas, cria tabelas no startup
│   ├── config.py            # lê variáveis do .env
│   ├── db.py                # engine do banco + criação automática de tabelas
│   ├── models.py            # tabelas: Fase, Participacao, Partida, AnaliseResultado
│   ├── client_java.py       # chamadas HTTP pro back Java (com paginação de rodadas)
│   ├── sync_service.py      # sync completo: busca dados, popula banco, recalcula
│   ├── calculo/
│   │   ├── forca.py         # score de força de cada time
│   │   ├── probabilidades.py # gols esperados (Poisson) por confronto
│   │   ├── monte_carlo.py   # simulação vetorizada (numpy) do restante da fase
│   │   └── pipeline.py      # orquestra o cálculo e monta o JSON final
│   └── routers/
│       ├── sync.py          # POST /fases/{id}/sync
│       ├── eventos.py       # POST /fases/{id}/eventos/partida-finalizada
│       └── analise.py       # GET  /fases/{id}/analise , GET /fases/{id}/status
├── requirements.txt
├── docker-compose.yml       # Postgres opcional
├── Dockerfile                # opcional, pra deploy do próprio microsserviço
└── .env.example
```

## 7. Observações importantes sobre o cálculo

- **Zonas**: como confirmado, as zonas são fixas por posição durante a fase.
  O range de posições de cada zona é inferido automaticamente a partir da
  ordem atual retornada por `/participacao-fase/fase/{faseId}` (ver
  `_mapear_zonas_por_posicao` em `pipeline.py`). Se o nome da zona de
  rebaixamento não contiver a palavra "rebaix" (case-insensitive), o campo
  `probRebaixamento` fica `null` — ajuste essa heurística em `pipeline.py`
  se sua convenção de nomes for diferente.
- **Critério de desempate**: réplica do `LinhaClassificacaoDTO` do back Java
  (pontos, saldo, vitórias, gols pró, gols contra, amarelos, vermelhos). O
  último critério do Java (confronto direto) **não** é simulado dentro do
  Monte Carlo — é um refinamento que dá bem mais trabalho de implementar
  corretamente numa simulação vetorizada; se notar muita distorção em
  empates apertados, me avise que a gente adiciona depois.
- **Fase encerrada**: quando todas as partidas de uma fase estiverem
  `realizada=true`, o campo `encerrada` fica `true` e a fase nunca mais é
  sincronizada nem recalculada (nem por evento, nem por sync manual, a
  menos que você chame `/sync?forcar=true` explicitamente).
- **Sem polling automático embutido**: o projeto não tem nenhum agendador
  rodando sozinho. O gatilho principal é o evento vindo do frontend. Se
  quiser um "sync de segurança" (ex: a cada X horas, ou quando o front
  percebe que `calculadoEm` está muito antigo), isso fica a critério de
  quando/como você quiser chamar `POST /fases/{id}/sync` — o endpoint já
  está pronto pra isso, só falta decidir o gatilho.
