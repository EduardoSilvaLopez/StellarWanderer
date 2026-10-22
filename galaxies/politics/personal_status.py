from __future__ import annotations

import logging

import galaxies.politics.political_entity as gppe
import galaxies.people.player as gpp


logger = logging.getLogger(__name__)

class PersonalStatus:
    def __init__(self, entity: gppe.PoliticalEntity) -> None:
        self.reputation: float = 1.0
        if entity is None:
            raise Exception("No political entity given")
        self.entity: gppe.PoliticalEntity = entity

    @staticmethod
    def deserialize(source: dict, entity_name: str) -> PersonalStatus:
        if entity_name == gppe.THOSE_WHO_SHARE.name:
            result: PersonalStatus = PersonalStatus(gppe.THOSE_WHO_SHARE)
        else:
            result: PersonalStatus = PersonalStatus(None)
        result.reputation = source['reputation']
        return result

    def serialize(self) -> dict:
        return {'reputation': self.reputation}

    def adjust_reputation_by_supply(self, key: str, quantity: float) -> None:
        if key not in self.entity.exchange_reputation_changes:
            logger.warning(f"No reputation changes defined for '{key}' in {self.name}")
            return
        old_rep: float = gpp.current_player.those_who_share.reputation
        change: float = self.entity.exchange_reputation_changes[key] * quantity
        new_rep: float = old_rep + change
        logger.info(f"Reputation in {self.entity.name} changed: {old_rep} + {change} = {new_rep}.")
        gpp.current_player.those_who_share.reputation = new_rep

