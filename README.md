# Automação de produção de vídeo

Reconstrução incremental em Python. As Etapas 1 e 2 entregam a base modular e
providers de assets para **Pixabay, Unsplash e Wikimedia Commons**. Os providers
buscam metadados e baixam arquivos usando o mesmo contrato `AssetProvider`.
Não há implementação de LLM/Groq, Visual Planner, Fish Audio, narração, edição,
composição de vídeo ou orquestração do pipeline nesta etapa.

## Instalação

Python **3.11 ou superior**. Na raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env     # Windows PowerShell: Copy-Item .env.example .env
```

Dependências de execução: HTTPX para HTTP assíncrono, Pydantic para modelos e
pydantic-settings para configuração. O extra `dev` instala Ruff. Os testes usam
`unittest` do Python e `httpx.MockTransport`; não precisam de rede ou credenciais.

## Estrutura

```text
.
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── scripts/
│   └── check_asset_integrations.py
├── src/video_production/
│   ├── config.py
│   ├── domain/models.py
│   ├── assets/
│   │   ├── interfaces.py
│   │   ├── errors.py
│   │   └── providers/
│   │       ├── _base.py
│   │       ├── pixabay.py
│   │       ├── unsplash.py
│   │       └── wikimedia.py
│   ├── llm/
│   ├── planner/
│   ├── references/
│   ├── narration/
│   ├── composition/
│   └── py.typed
└── tests/
    ├── provider_fixtures.py
    ├── test_asset_providers.py
    ├── test_asset_downloads.py
    ├── test_config.py
    ├── test_models.py
    └── test_interfaces.py
```

Os pacotes contêm seus `__init__.py`. Os módulos `llm`, `planner`, `references`,
`narration` e `composition` mantêm somente as interfaces da Etapa 1. `domain` não
importa providers concretos. `AssetProvider` continua sendo um `typing.Protocol`
com `async search(AssetQuery) -> tuple[Asset, ...]` e
`async download(Asset, destination: Path) -> Path`.

## Configuração

`Settings()` carrega argumentos explícitos > ambiente > `.env` > padrões.
Importar o pacote não faz requisições. `.env` e caminhos relativos usam o diretório
atual; `_env_file=None` desativa a leitura de arquivo. O `.env` é ignorado pelo Git.

| Variável | Padrão / uso |
| --- | --- |
| `PIXABAY_API_KEY` | Sem padrão; necessária para Pixabay |
| `UNSPLASH_ACCESS_KEY` | Sem padrão; necessária para Unsplash |
| `VIDEO_USER_AGENT` | `Automa-o-Scrapping/0.2 (+https://github.com/rmeles879-coder/Automa-o-Scrapping)` |
| `VIDEO_HTTP_TIMEOUT_SECONDS` | `30`; timeout de conexão/leitura/escrita HTTP |
| `VIDEO_ENV` | `development`; também aceita `test` e `production` |
| `VIDEO_LOG_LEVEL` | `INFO`; também aceita `DEBUG`, `WARNING`, `ERROR`, `CRITICAL` |
| `VIDEO_OUTPUT_DIR` | `output` |
| `VIDEO_CACHE_DIR` | `.cache/video-production` |

Preencha as duas credenciais **somente no ambiente ou `.env` local**. O exemplo
versionado deixa seus valores vazios. Chaves são `SecretStr`, não aparecem no
`repr` ou na serialização de `Settings`. Chaves ausentes não impedem o Commons;
instanciar Pixabay/Unsplash sem sua chave gera `ProviderConfigurationError`.
O Commons não usa API key e envia um `User-Agent` identificável em todas as chamadas.
É possível substituir o agente pelo nome/URL de contato da aplicação.
`log_level`, `cache_dir` e `output_dir` continuam sendo configuração para consumo;
esta etapa não instala handlers de logging nem implementa cache persistente.

## Providers

| Provider | Tipos de mídia | API e autenticação |
| --- | --- | --- |
| `PixabayProvider` | Imagens e vídeos | `/api/` e `/api/videos/`; chave no parâmetro `key` |
| `UnsplashProvider` | Imagens | `/search/photos`; `Authorization: Client-ID ...`, versão `v1` |
| `WikimediaCommonsProvider` | Imagens, vídeos e áudio | MediaWiki Action API, namespace de arquivos; `User-Agent` |

Pixabay e Unsplash rejeitam tipos não suportados antes de chamar HTTP. Pixabay
seleciona a maior variante de vídeo disponível. Unsplash respeita o máximo de
30 itens por página. Commons consulta `imageinfo`/`extmetadata`, mantém a ordem da
busca e filtra os tipos de mídia. Unsplash e Commons percorrem até quatro páginas
para preencher o limite solicitado, sem duplicar IDs. O limite é um máximo:
resultados filtrados, arquivos incompletos ou fim da busca podem produzir menos itens.

### Modelo normalizado

Todos os providers retornam `Asset` com os mesmos campos:

| Campo | Significado |
| --- | --- |
| `id` | Identificador do serviço; use `(source, id)` para identificar globalmente |
| `source` | `pixabay`, `unsplash` ou `wikimedia_commons` |
| `media_type` | `image`, `video` ou `audio` |
| `title`, `description` | Texto da API; descrição/alt text/tags/nome do arquivo como fallback |
| `tags` | Tupla de tags/categorias sem repetições |
| `thumbnail_url` | URL de miniatura, quando disponível |
| `download_url` | URL da mídia, separada da página de origem |
| `source_page_url` | Página original, quando informada |
| `author` | Nome do autor, quando informado |
| `license` | `AssetLicense`: nome, URL da licença e atribuição disponível |
| `width`, `height` | Dimensões informadas pela API; ausentes ficam `None` |
| `duration_seconds` | Duração quando informada, atualmente em vídeos Pixabay |
| `download_tracking_url` | Endpoint público de rastreamento de download do Unsplash |

Os dados do Commons são convertidos de HTML para texto simples. A licença é
preservada por arquivo; metadados ausentes ficam `Unknown`, sem assumir domínio
público. Pixabay usa **Pixabay Content License** e Unsplash usa **Unsplash License**.
Metadados de licença não substituem a avaliação das condições de uso do asset.
Dimensões descrevem os metadados da API; versões redimensionadas podem diferir.

Construções antigas com `provider`, `kind` e `uri` continuam aceitas, e esses nomes
seguem disponíveis como propriedades de leitura. A serialização usa `source`,
`media_type` e `download_url`. Os demais modelos e contratos da Etapa 1 permanecem
imutáveis e validados; caminhos declarativos não abrem arquivos por si mesmos.

### Exemplo de uso

Com a credencial Pixabay configurada no ambiente:

```python
import asyncio
from pathlib import Path

from video_production.assets import AssetProvider, PixabayProvider
from video_production.domain.models import AssetQuery


async def main():
    async with PixabayProvider() as provider:
        assets_provider: AssetProvider = provider
        assets = await assets_provider.search(AssetQuery(query="nature", limit=3))
        for asset in assets:
            print(asset.source, asset.id, asset.title, asset.license.name)
        if assets:
            await assets_provider.download(assets[0], Path("output/nature.jpg"))


asyncio.run(main())
```

Substitua por `UnsplashProvider()` ou `WikimediaCommonsProvider()` para outras
fontes. O Commons funciona sem chaves. Instâncias aceitam `settings=Settings(...)`
e `client=httpx.AsyncClient(...)` para injeção; o chamador fecha clientes injetados.
Use `async with` ou `await provider.aclose()` para fechar o cliente criado pelo provider.

Downloads criam o diretório de destino e usam um arquivo temporário no mesmo
filesystem. O destino completo é substituído somente após receber o arquivo;
falhas não deixam arquivos parciais nem alteram um destino existente. As chaves
da API não são enviadas nos pedidos de download dos arquivos de mídia.

Unsplash registra o download por `links.download_location` antes de obter a mídia
e usa a URL devolvida pela API. Esse endpoint deve pertencer a `api.unsplash.com`.
Ao exibir imagens Unsplash, preserve as URLs de hotlink fornecidas e a atribuição
com links ao autor/Unsplash, conforme as [diretrizes da API](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines).
Em uma aplicação de produção, implemente cache/respeito aos limites dos serviços
antes de fazer buscas repetidas; não há retries ou cache automático nesta etapa.

### Erros

`AssetProviderError` agrupa configuração, tipo de mídia, transporte, status HTTP,
resposta inválida e gravação local. `ProviderHTTPError.status_code` permite tratar
401/403/429/5xx. Os erros públicos omitem corpo e URL autenticada, e falhas de
transporte não encadeiam exceções que poderiam revelar a chave do Pixabay.
Não habilite logs de requests autenticadas com dados sensíveis na aplicação.

## Verificação

Testes unitários, incluindo respostas HTTP simuladas:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

A suíte cobre configuração, modelo comum e compatibilidade, normalização das três
APIs, paginação, tipos suportados, erros HTTP/JSON/timeout, metadados opcionais,
licenças, rastreamento Unsplash, downloads e preservação de arquivos em falhas.
Todas as respostas HTTP de testes são simuladas; as chaves nas fixtures são
valores artificiais sem uso fora da suíte.

Teste real **opt-in**, separado da suíte, com as credenciais no ambiente e os
hosts permitidos pela rede:

```bash
python scripts/check_asset_integrations.py --query nature
```

O script busca um item por integração: imagens e vídeos Pixabay, imagens Unsplash
e imagens Commons. Não baixa mídia nem imprime chaves/URLs autenticadas. Retorna
`0` quando as chamadas disponíveis terminam sem erro (ou são puladas por falta de
configuração), `1` para erro HTTP/resposta e `2` para transporte indisponível.
O JSON diferencia `ok`, `skipped_missing_configuration`, `unavailable_network`
e falhas; uma chamada indisponível não é apresentada como integração validada.

## Etapas futuras

A implementação de LLM, planner visual, análise de referências, narração,
composição e pipeline será feita em etapas posteriores. Esta entrega implementa
somente os providers de assets e sua infraestrutura/testes.
