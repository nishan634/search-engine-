import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi = get_asgi_application()
# HTTP only for now; add websocket routes here when real-time streaming is needed.
application = ProtocolTypeRouter({"http": django_asgi})
