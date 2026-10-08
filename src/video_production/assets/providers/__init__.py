"""Providers concretos de assets disponíveis nesta etapa."""

from .pixabay import PixabayProvider
from .unsplash import UnsplashProvider
from .wikimedia import WikimediaCommonsProvider

__all__ = ["PixabayProvider", "UnsplashProvider", "WikimediaCommonsProvider"]
