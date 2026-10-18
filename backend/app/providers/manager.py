from app.providers.base import BaseProvider
from app.providers.instagram_provider import InstagramProvider
from app.providers.ytdlp_provider import YtdlpProvider

class ProviderManager:
    def __init__(self):
        # Dedicated platform providers take priority, falling back to YtdlpProvider
        self.providers = [
            InstagramProvider(),
            YtdlpProvider()
        ]

    def get_provider_for_url(self, url: str) -> BaseProvider:
        for provider in self.providers:
            if provider.can_handle(url):
                return provider
        
        # Fallback to the generic YtdlpProvider
        return self.providers[-1]

provider_manager = ProviderManager()
