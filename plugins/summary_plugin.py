"""
Example Plugin: Adds a summary command.
"""

from src.core.plugin_base import PluginBase


class SummaryPlugin(PluginBase):
    name = "summary"
    version = "1.0"
    overrides = []  # No overrides

    def register_hooks(self, registry):
        # Example: Hook into note addition
        registry.register_hook("post_add_note", self.on_note_added)

    def get_commands(self):
        return {
            "summary": self.summary_command
        }

    def on_note_added(self, note):
        print(f"Plugin: Note '{note.title}' added!")

    def summary_command(self):
        print("Total notes: (placeholder)")