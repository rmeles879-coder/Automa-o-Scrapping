# Automação de produção de vídeo

Primeira etapa da reconstrução incremental do projeto: um pacote Python modular
com configuração, modelos validados e contratos para futuras implementações.
**Nenhuma API externa está implementada e nenhuma API key é necessária.**
Ainda não há CLI, pipeline executável, scraping, download, análise real, narração
ou renderização de vídeo.

## Requisitos e instalação

Python **3.11 ou superior**. Na raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env     # Windows PowerShell: Copy-Item .env.example .env
```

As dependências de execução são Pydantic (validação dos modelos) e
pydantic-settings (configuração). O extra `dev` instala Ruff. Os testes usam
`unittest`, incluído no Python. Não são necessários FFmpeg, SDKs de providers
nem credenciais.

## Estrutura

```text
.
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── src/
│   └── video_production/
│       ├── __init__.py
│       ├── py.typed
│       ├── config.py
│       ├── domain/
│       │   ├── __init__.py
│       │   └── models.py
│       ├── assets/
│       ├── llm/
│       ├── planner/
│       ├── references/
│       ├── narration/
│       └── composition/
└── tests/
    ├── test_config.py
    ├── test_models.py
    └── test_interfaces.py
```

Cada módulo funcional contém `__init__.py` e `interfaces.py`. `domain` é o
vocabulário comum e não importa os demais módulos. Não há providers concretos
nesta etapa. Os contratos usam `typing.Protocol`: implementações futuras podem
ser injetadas pelo consumidor sem herança obrigatória. Os métodos são `async`
para acomodar I/O futuro; nenhum método faz uma chamada externa agora.

## Fronteiras da arquitetura

| Módulo | Interface | Entrada → saída | Responsabilidade futura |
| --- | --- | --- | --- |
| `assets` | `AssetProvider` | `AssetQuery` → assets; asset + destino → caminho | Buscar metadados e obter arquivos |
| `llm` | `LLMProvider` | `LLMRequest` → `LLMResponse` | Isolar cada fornecedor de LLM |
| `references` | `ReferenceAnalyzer` | `VisualReference` → `ReferenceAnalysis` | Descrever referências visuais locais |
| `planner` | `VisualPlanner` | `VideoBrief` + análises → `VisualPlan` | Planejar cenas e consultas de assets |
| `narration` | `NarrationProvider` | `NarrationRequest` + destino → `AudioTrack` | Sintetizar narração em etapa futura |
| `composition` | `VideoComposer` | `CompositionRequest` → `VideoArtifact` | Compor arquivos locais em etapa futura |

Fluxo previsto: roteiro e referências → análises → plano visual → seleção e
obtenção de assets → narração opcional → composição. Um planner futuro poderá
receber um `LLMProvider` por injeção. O orquestrador e os adaptadores concretos
serão adicionados em etapas posteriores; este fluxo ainda não é executável.

Os modelos rejeitam campos desconhecidos e alterações após a criação. Durações,
dimensões e FPS devem ser positivos; durações devem ser finitas. Um plano possui
cenas em sequência, IDs únicos e duração calculada pela soma das cenas. A duração
alvo do briefing orienta o planner; não há ajuste automático de duração nesta
etapa. A composição aceita no máximo uma mídia por cena e valida seus IDs.
Os caminhos são declarativos: modelos não verificam existência nem criam arquivos.
Assets exigem metadados de licença, cuja adequação de uso deverá ser verificada
pelas implementações futuras.

## Configuração

```python
from video_production.config import Settings

settings = Settings()
print(settings.output_dir)
```

| Variável | Padrão | Valores |
| --- | --- | --- |
| `VIDEO_ENV` | `development` | `development`, `test`, `production` |
| `VIDEO_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `VIDEO_OUTPUT_DIR` | `output` | Caminho para resultados futuros |
| `VIDEO_CACHE_DIR` | `.cache/video-production` | Caminho para cache futuro |

A configuração é carregada apenas ao instanciar `Settings`. A precedência é:
argumentos explícitos > variáveis de ambiente > `.env` > padrões. O `.env` e
caminhos relativos são resolvidos a partir do diretório atual. É possível passar
`Settings(_env_file="caminho/.env")` ou `_env_file=None` para não ler arquivo.
Campos extras no `.env` são ignorados. Não há criação de diretórios nem configuração
global de logging; `log_level` fica disponível para um futuro ponto de entrada.

O `.env` é ignorado pelo Git. O `.env.example` contém apenas configuração não
sensível. Não adicione credenciais ao código, documentação ou arquivos versionados.

## Exemplo local de modelos

```python
from video_production.domain.models import ScenePlan, VisualPlan

plan = VisualPlan(scenes=(
    ScenePlan(
        id="opening",
        duration_seconds=5,
        visual_description="Plano aberto de uma cidade ao amanhecer",
        narration="Um novo dia começa.",
    ),
))
print(plan.duration_seconds)  # 5.0
print(plan.model_dump_json(indent=2))
```

Este exemplo apenas constrói dados em memória. Não analisa imagens, consulta
providers nem produz vídeo.

## Verificação

Após instalar o pacote:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

Os testes cobrem configuração e precedência, validação e serialização dos modelos,
consistência do plano e das mídias e uso de uma interface com um provider em memória.
São executados sem APIs externas, arquivos de mídia ou API keys.

## Escopo das próximas etapas

Providers de assets e LLM, implementação do planner, análise visual, narração,
composição e orquestração serão desenvolvidos incrementalmente. Nenhuma dessas
implementações integra esta entrega inicial.
