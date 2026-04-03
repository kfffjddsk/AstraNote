"""
AstraNote Plugin Base

Defines interfaces for plugins.
"""

from abc import ABC, abstractmethod
from typing import Dict, Callable


class PluginBase(ABC):
    """
    Base class for all plugins.
    """

    name: str
    version: str
    overrides: list = []  # List of features this plugin overrides

    @abstractmethod
    def register_hooks(self, registry):
        """Register hooks with the plugin registry."""
        pass

    def get_commands(self) -> Dict[str, Callable]:
        """Return additional CLI commands (optional)."""
        return {}


class PluginRegistry:
    """
    Manages loaded plugins and their hooks.
    """

    def __init__(self):
        self.hooks = {}
        self.plugins = []

    def register_plugin(self, plugin: PluginBase):
        """Register a plugin and its hooks."""
        self.plugins.append(plugin)
        plugin.register_hooks(self)

    def register_hook(self, hook_name: str, func: Callable):
        """Register a hook function."""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(func)

    def call_hook(self, hook_name: str, *args, **kwargs):
        """Call all registered hooks for a name."""
        if hook_name in self.hooks:
            for func in self.hooks[hook_name]:
                func(*args, **kwargs)