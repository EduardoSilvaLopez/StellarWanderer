import logging; logger = logging.getLogger(__name__)

from Galaxies import OreField

class OreMine:
    def __init__(
            self,
            parent_field: OreField,
            longitude: int = 0,
            latitude: int = 0,
            orientation: float = 0.0,
            saved_attributes: dict = None
            ):
        self.parent_field: OreField = parent_field
        if saved_attributes is None:
            self.longitude: float = longitude
            self.latitude: float = latitude
            self.orientation: float = orientation
            self.content: int = 0
        else:
            self.longitude: float = saved_attributes['longitude']
            self.latitude: float = saved_attributes['latitude']
            self.orientation: float = saved_attributes['orientation']
            self.content: int = saved_attributes['content']
        logger.info(f"Ore Mine created at {self.longitude}, {self.latitude}. Content: {self.content}.")

    def serialize(self) -> dict:
        return {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'orientation': self.orientation,
            'content': self.content
            }
