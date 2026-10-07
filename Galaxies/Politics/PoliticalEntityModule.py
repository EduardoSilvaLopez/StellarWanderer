class PoliticalEntity:
    def __init__(self, name: str, color: tuple, icon: str):
        self.name = name
        self.color = color
        self.icon = icon

THOSE_WHO_SHARE: PoliticalEntity = PoliticalEntity(
        "Those-Who-Share",
        (128, 0, 0),
        "PoliticalEntity.1.png"
    )