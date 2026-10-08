"""Erros públicos não incluem URL de requisição, corpo HTTP ou credenciais."""


class AssetProviderError(Exception):
    """Base dos erros de providers de assets."""


class ProviderConfigurationError(AssetProviderError):
    """Configuração ausente ou incompatível com o provider."""


class UnsupportedMediaTypeError(AssetProviderError):
    """Tipo de mídia não suportado pelo provider."""


class ProviderNetworkError(AssetProviderError):
    """Timeout ou falha de transporte."""


class ProviderHTTPError(AssetProviderError):
    """Status HTTP de erro; não mantém o objeto de requisição autenticada."""

    def __init__(self, source: str, status_code: int):
        self.source = source
        self.status_code = status_code
        super().__init__(f"{source}: HTTP {status_code}")


class ProviderResponseError(AssetProviderError):
    """JSON ou metadados não correspondem ao formato esperado."""


class AssetDownloadError(AssetProviderError):
    """Falha ao salvar o arquivo local."""
