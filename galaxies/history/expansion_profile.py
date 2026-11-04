class ExpansionProfile:
    """How an entity expands: the odds of founding a star or a settlement, the size a system needs before it founds a
    star, and the speed of its technology."""

    def __init__(
            self,
            entity: str,
            slots_for_new_star: int,
            slots_for_new_settlement: int,
            size_for_new_star: int,
            tech_factor: float
            ) -> None:
        self.entity = entity
        self.slots_for_new_star = slots_for_new_star
        self.slots_for_new_settlement = slots_for_new_settlement
        self.size_for_new_star = size_for_new_star
        self.tech_factor = tech_factor

LowTechImperialist = ExpansionProfile("The Shining Throne", 6, 10, 105, 0.8)
TechConservative = ExpansionProfile("Those-Who-Share", 2, 8, 195, 1)
TechOrganic = ExpansionProfile("United Diversity", 4, 6, 270, 1)
