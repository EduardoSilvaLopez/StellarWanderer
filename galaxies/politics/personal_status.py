from __future__ import annotations

import logging

import galaxies.politics.political_entity as gppe


logger = logging.getLogger(__name__)

class PersonalStatus:
    def __init__(self, entity: gppe.PoliticalEntity) -> None:
        self.reputation: float = 1.0
        self.flags: set[str] = set()  # simple strings the entity's dealings set
        if entity is None:
            raise Exception("No political entity given")
        self.entity: gppe.PoliticalEntity = entity

    @staticmethod
    def deserialize(source: dict, entity_name: str) -> PersonalStatus:
        if entity_name == gppe.THOSE_WHO_SHARE.name:
            result: PersonalStatus = PersonalStatus(gppe.THOSE_WHO_SHARE)
        else:
            raise Exception(f"Unknown entity: '{entity_name}'")
        result.reputation = source['reputation']
        result.flags = set(source.get('flags', []))  # optional in a save: saves made before flags had none
        return result

    def serialize(self) -> dict:
        return {'reputation': self.reputation, 'flags': sorted(self.flags)}

    def adjust_reputation_by_supply(self, key: str, quantity: float) -> None:
        '''Positive quantities increase reputation ('giving'), negative ones decrease it ('taking').'''
        if key not in self.entity.exchange_reputation_changes:
            logger.warning(f"No reputation changes defined for '{key}' in {self.entity.name}")
            return
        if quantity == 0.0:
            return
        old_rep: float = self.reputation
        change: float = self.entity.exchange_reputation_changes[key] * quantity
        new_rep: float = old_rep + change
        logger.info(
            f"Reputation in {self.entity.name} changed because of {key}: {old_rep:.6f} + {change:.6f} = {new_rep:.6f}."
            )
        self.reputation = new_rep

