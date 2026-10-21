"""Modal dialogs shown above the game (or alone, at startup)."""

from .dialog import Dialog, DialogResult, run_in_window
from .message_dialog import MessageDialog
from .messages import Message, confirm, show_message, next_pending_message
from .starting_dialog import StartingDialog
from .knowledge_dialogs import KnownSystemsDialog, KnownPeopleDialog
from .mission_board_dialog import MissionBoardDialog, PendingMissionsDialog

__all__ = [
    "Dialog", "DialogResult", "run_in_window", "StartingDialog", "MessageDialog", "KnownSystemsDialog",
    "KnownPeopleDialog", "MissionBoardDialog", "PendingMissionsDialog",
    "Message", "confirm", "show_message", "next_pending_message",
]
