from app.providers.base import BaseProvider
from app.providers.ytdlp_provider import YtdlpProvider

class ProviderManager:
    def __init__(self):
        # In a highly modular design, we could load distinct platform modules here.
        # Since YtdlpProvider wraps yt-dlp which is a generic extractor, it acts as a
        # unified engine, but we register it and can easily extend this list.
        self.providers = [
            YtdlpProvider()
        ]

    def get_provider_for_url(self, url: str) -> BaseProvider:
        for provider in self.providers:
            if provider.can_handle(url):
                return provider
        
        # Fallback to the generic YtdlpProvider
        return self.providers[0]

provider_manager = ProviderManager()
