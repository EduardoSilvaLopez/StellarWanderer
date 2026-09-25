from Galaxies import OreField

class OreMine:
    def __init__(self, parent_field: OreField, longitude: int, latitude: int, saved_properties: dict, **args):
        self.parent_field: OreField = parent_field
        self.longitude: float = longitude
        self.latitude: float = latitude
        if saved_properties is None:
            self.orientation: float = args[0]
            self.content: int = args[1]

    def serialize(self) -> dict:
        return {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'orientation': self.orientation,
            'content': self.content,
            }

