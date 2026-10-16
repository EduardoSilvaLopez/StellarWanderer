class PersonalStatus:
    def __init__(self):
        self.reputation: float = 1.0    

    @staticmethod
    def deserialize(source: dict) -> PersonalStatus:
        result: PersonalStatus = PersonalStatus()
        result.reputation = source['reputation']
        return result

    def serialize(self) -> dict:
        return {'reputation': self.reputation}