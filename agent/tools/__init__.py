# Import all tools to register them
from . import filesystem
from . import shell
from . import web
from . import memory
from . import code

from .base import registry

def get_registry():
    return registry

__all__ = ["registry", "get_registry"]
