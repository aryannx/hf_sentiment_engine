from __future__ import annotations

from typing import Iterable

from src.middle_office.ibor import IBOR
from src.middle_office.models import CorporateAction


def apply_corporate_actions(ibor: IBOR, actions: Iterable[CorporateAction]) -> None:
    """Apply a list of corporate actions to the IBOR."""
    for action in actions:
        ibor.apply_corporate_action(action)

