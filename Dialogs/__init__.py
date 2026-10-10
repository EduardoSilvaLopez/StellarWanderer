"""Modal dialogs shown above the game (or alone, at startup)."""

from .dialog import Dialog, DialogResult, run_in_window
from .message_dialog import MessageDialog
from .messages import show_message, next_pending_message, has_pending_messages
from .starting_dialog import StartingDialog

__all__ = [
    "Dialog", "DialogResult", "run_in_window", "StartingDialog", "MessageDialog",
    "show_message", "next_pending_message", "has_pending_messages",
]
