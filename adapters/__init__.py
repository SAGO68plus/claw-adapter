"""Adapter registry — auto-discovers and manages all adapters."""
from typing import Dict
from .base import BaseAdapter
from .openclaw import OpenClawAdapter
from .sillytavern import SillyTavernAdapter
from .claude_code_router import ClaudeCodeRouterAdapter

# Register all adapters here. To add a new one:
# 1. Create adapters/myservice.py inheriting BaseAdapter
# 2. Import and add to _BUILTIN below
_BUILTIN = [
    OpenClawAdapter(),
    SillyTavernAdapter(),
    ClaudeCodeRouterAdapter(),
]

_registry: Dict[str, BaseAdapter] = {}

def _init():
    for a in _BUILTIN:
        _registry[a.id] = a

_init()

def get_adapter(adapter_id: str) -> BaseAdapter | None:
    return _registry.get(adapter_id)

def all_adapters() -> Dict[str, BaseAdapter]:
    return dict(_registry)

def register(adapter: BaseAdapter):
    _registry[adapter.id] = adapter
