from __future__ import annotations
from typing import List, Optional

import random
import pygame

from common.paths import resource_path
import logging

from galaxies.people.person import Ethnicity
import galaxies.politics.expansion_profile as ep

logger = logging.getLogger(__name__)

class PoliticalEntity:
    def __init__(
            self, name: str,
            color: tuple,
            icon_filename: str,
            expansion_profile: ep.ExpansionProfile,
            titles: dict,
            settlement_names_1: List[str],
            settlement_names_2: List[str],
            exchange_reputation_changes: dict,
            biggest_cities: List[tuple],
            planets: List[(str)],
            portal_base_names: List[(str)],
            hobbies_sociable: List[(str)],
            hobbies_asocial: List[(str)],
            ) -> None:
        self.name: str = name
        self.color: tuple = color
        self.icon: Optional[pygame.Surface] = None
        self._load_icon(icon_filename)
        self.expansion_profile: ep.ExpansionProfile = expansion_profile
        self.titles = titles
        self.settlement_names_1: List[str] = settlement_names_1
        self.settlement_names_2: List[str] = settlement_names_2
        self.exchange_reputation_changes: dict = exchange_reputation_changes
        self.settlements = biggest_cities
        self.planets = planets
        self.portal_base_names = portal_base_names
        self.hobbies_sociable: List[str] = hobbies_sociable  # what the people do for fun (see Person._generate_hobby)
        self.hobbies_asocial: List[str] = hobbies_asocial  # the same, for people with sociability below 20

    def title_for(self, reputation: float) -> str:
        # The lowest title has no limit (-inf), so there is always one: the default is never used.
        return next((self.titles[k] for k in sorted(self.titles, reverse=True) if reputation >= k), '')

    def title_floor(self, reputation: float) -> float:
        """The lowest reputation that keeps the title `reputation` gives: its threshold (-inf for the lowest one)."""
        return max((k for k in self.titles if reputation >= k), default=float('-inf'))

    def _load_icon(self, icon_filename: str) -> None:
        """Load the icon image from common/resources/textures."""
        icon_path = resource_path('textures', icon_filename)
        try:
            self.icon = pygame.image.load(icon_path)
        except Exception as e:
            print(f"Warning: Could not load political entity icon {icon_filename}: {e}")

    def generate_outpost_name(self, my_random: random.Random) -> str:
        return self.settlement_names_1[my_random.randint(0, len(self.settlement_names_1) - 1)]\
            + " " + self.settlement_names_2[my_random.randint(0, len(self.settlement_names_2) - 1)]

UNITED_DIVERSITY: PoliticalEntity = PoliticalEntity(
        name="United Diversity",
        color=(100, 100, 230),
        icon_filename="PoliticalEntity.UnitedDiversity.png",
        expansion_profile=ep.TechOrganic,
        titles={
         float('-inf'): 'Prisoner',
            0: 'Citizen',
            100: 'Mister',
        },
        settlement_names_1=[
            "AFAIK",
            "FAFO",
            "GOAT",
            "LOL",
            "NA",
            "ORLY",
            "TBD",
            "WTF",
        ],
        settlement_names_2=[
            "",
        ],
        exchange_reputation_changes={
            "maintenance": 0.0,
            "energy": 0.0,
            "credits": 0.0,
            "air": 0.001,
            "water": 0.001,
            "food": 0.001,
            "mines": 0.0,
            "ore": 0.0,
            "raw_water": 0.01,
        },
        biggest_cities=[
            ('Carela ', Ethnicity.WHITE),
        ]
        , planets= [
            'Moon',
            'Mars',
        ]
        , portal_base_names= [
            "Prime",
        ]
        , hobbies_sociable= [
            "TBD",
        ]
        , hobbies_asocial= [
            "TBD",
        ]
    )

THOSE_WHO_SHARE: PoliticalEntity = PoliticalEntity(
        name="Those-Who-Share",
        color=(230, 100, 100),
        icon_filename="PoliticalEntity.ThoseWhoShare.png",
        expansion_profile=ep.TechConservative,
        titles={
         float('-inf'): 'Prisoner',
            -30: 'Dependent',
            -10: 'Student',
            0: 'Pioneer',
            10: 'Citizen',
            20: 'Comrade',
            50: 'Companion',
            100: 'Forebear',
            200: 'Guardian',
            500: 'Herald',
            1000: 'Steward', # Xi
            2000: 'Hero',
            5000: 'Champion',
            10000: 'Premier'
        },
        settlement_names_1=[
            "Arduous",
            "Beneficial",
            "Burdensome",
            "Challenging",
            "Commendable",
            "Conscientious",
            "Constructive",
            "Dedicated",
            "Demanding",
            "Edifying",
            "Enriching",
            "Essential",
            "Exacting",
            "Formidable",
            "Gratifying",
            "Honorable",
            "Industrious",
            "Laborious",
            "Laudable",
            "Meritorious",
            "Momentous",
            "Pressing",
            "Responsible",
            "Rigorous",
            "Salutary",
            "Strenuous",
            "Uplifting",
            "Weighty",
            "Worthwhile"
        ],
        settlement_names_2=[
            "Achievement",
            "Aim",
            "Assignment",
            "Charge",
            "Chore",
            "Deed",
            "Duty",
            "End",
            "Endeavor",
            "Errand",
            "Feat",
            "Goal",
            "Hope",
            "Issue",
            "Milestone",
            "Mission",
            "Objective",
            "Obligation",
            "Outcome",
            "Plan",
            "Project",
            "Purpose",
            "Quest",
            "Reality",
            "Requirement",
            "Result",
            "Target",
            "Task",
            "Undertaking",
            "Venture",
            "Vocation",
            "Work"
        ],
        exchange_reputation_changes={
            "maintenance": 24.0,
            "energy": 5e-13,
            "credits": 100.0,
            "air": 0.0006,
            "water": 0.0003,
            "food": 0.0006,
            "mines": 5.0,
            "ore": 0.008,
            "raw_water": 0.001,
        },
        biggest_cities=[
            ('Jiùjīnshān, Ài', Ethnicity.BLACK),
            ('Niǔyuē, Shèqū', Ethnicity.BLACK),
            ('Bālí, Tón-lǐ-xīn', Ethnicity.WHITE),
            ('Bólín, Ài', Ethnicity.WHITE),
            ('Mòxīgē, Ài', Ethnicity.LATIN),
            ("Shèngbǎoluó, Xǐ'ài", Ethnicity.LATIN),
            ('Mǎdélǐ, Shèqū', Ethnicity.LATIN),
            ('Togyo, Ài', Ethnicity.ASIAN),
            ('Sel, Shèqū', Ethnicity.ASIAN),
            ('Shangha, Shèqū', Ethnicity.ASIAN),
            ('Bejing, Ài', Ethnicity.ASIAN),
            ('Chenzhen, Tón-lǐ-xīn', Ethnicity.ASIAN),
            ('Singapa, Tón-lǐ-xīn', Ethnicity.ASIAN),
            ('Guanzhou, Ài', Ethnicity.ASIAN),
            ('Xīn-xīàng, Tón-lǐ-xīn', Ethnicity.ASIAN),
            ("Pínděng, Xǐ'ài", Ethnicity.ASIAN),
            ('Tuánjié, Ài', Ethnicity.ASIAN),
            ('Lanfang-dexī, Tuánjié', Ethnicity.ASIAN),
            ('Wei-de-xīwàng, Tuánjié', Ethnicity.ASIAN),
            ('Kǎisèlín, Ài', Ethnicity.ASIAN),
            ('Àidéhuá-duō, Guānhái', Ethnicity.ASIAN),
            ('Dàshān, Guānhái', Ethnicity.ASIAN),
            ('Huǒshānkǒu, Bānzhù', Ethnicity.ASIAN),
        ]
        , planets= [
            'Ài',
            'Shèqū',
            'Tón-lǐ-xīn',
            "Xǐ'ài",
            'Tuánjié',
            'Guānhái',
            'Bānzhù',
        ]
        , portal_base_names= [
            "Affection",
            "Altruism",
            "Benignity",
            "Benignacy",
            "Compassion",
            "Consideration",
            "Cordiality",
            "Decency",
            "Empathy",
            "Forgiveness",
            "Goodwill",
            "Hospitality",
            "Humanism",
            "Humility",
            "Kindness",
            "Patience",
            "Philanthropy",
            "Softness",
            "Solicitude",
            "Sympathy",
            "Sweetness",
            "Tenderness",
            "Tolerance",
            "Understanding",
            "Unselfishness",
        ]
        , hobbies_sociable= [
            "I like to walk in the hydroponic gardens.",
            "I enjoy people-watching in the transit hubs. Don't tell anyone.",
            "I like to try new foods in the main square.",
            "I like to try travel to other towns and cities.",
            "I spend time listening to street musicians.",
            "I enjoy reading old novels in the public lounges.",
            "I like to meditate in my balcony.",
            "I enjoy attending the quarter's theater plays.",
            "I like to collect vintage posters.",
            "I enjoy cooking with imported ingredients, you know, from the Throne or UniDiv. I know.",
            "I like to volunteer caring about the street plants.",
            "I enjoy playing board games with friends.",
            "I like to take long walks along the dome's perimeter paths when it's local night.",
            "I enjoy watching the weather cycles in cities. Those guys have some creativity.",
            "I like to sketch the architecture from the founding times. We are losing it, slowly.",
            "I like to practice indoor climbing when the gravity is big enough.",
            "I enjoy swimming in the municipal reservoirs.",
            "I enjoy watching PreDis movies. The animals! They had so many!",
            "I am fascinated by the Chen-Ning rebellion of 290. Those were brave people, and not Surnemals at all.",
            "I like to fly micro-drones in the recreation halls.",
            "I have my domouse. Caring about it is my hobbie.",
            "I enjoy tinkering with old household electronics, I have one from the post-war!",
            "I like to explore PreDis virtual landscapes.",
            "I enjoy watching shuttle departures from the observation decks.",
            "I like to practice gravity aerobics when the gym offers it.",
            "I enjoy restoring antique maps, from the first Martians for example.",
            "I like to attend debate nights in the civic forum, and I engage in the Assemblies.",
            "I enjoy participating in collaborative mural projects.",
            "I like to join the weekly storytelling circles.",
            "I enjoy dancing during the dome's festival nights.",
            "I like to help organize neighborhood events.",
            "I like to guide school groups through the hydroponic gardens. The children always ask about the water.",
            "I enjoy the poetry competitions in the central square, even when I don't win.",
            "I like to show my skills at the settlement's skill fairs. More skills, more duties, I know.",
            "I like to repair broken things for my neighbors. Useful things last.",
            "I enjoy the Sunday cooking nights at the canteen, where everyone brings a dish.",
            "I like to help build the floats for the Founders' Day parade.",
            "I enjoy the Assembly meetings at my workplace. Everyone's voice counts there.",
            "I like to tend the shared beds in the hydroponic gardens with my shift mates.",
            "I like to visit the factories on open days, to see what the Community makes.",
            "I enjoy the bench conversations in the square about the Community's future.",
            "I like to restore old machines for the workshops. Pride in what is useful.",
            "I enjoy the lectures at the civic school on Sunday mornings.",
        ]
        , hobbies_asocial= [
            "I like to be alone with my plants in the quiet corners of the gardens.",
            "I read at night, alone in my room.",
            "I walk the perimeter paths alone, when nobody is there.",
            "I tinker with old devices. I don't need help for that.",
            "I sleep as much as I can. It is my favorite thing.",
            "I watch the shuttles leave from the far end of the deck, alone.",
            "I sketch in a notebook. It's nobody's business.",
            "I fix my own clothes in the evening. Quietly.",
            "I don't really have hobbies. Work and rest are enough.",
            "I like the silence of the reservoirs at dawn.",
            "I cook for myself. Simple meals, no company.",
        ]
    )

THE_SHINING_THRONE: PoliticalEntity = PoliticalEntity(
        name="The Shining Throne",
        color=(100, 196, 196),
        icon_filename="PoliticalEntity.TheShiningThrone.png",
        expansion_profile=ep.LowTechImperialist,
        titles={
         float('-inf'): 'Prisoner',
            -100: 'Slave',
            0: 'Self',
            100: 'Servant',
            200: 'Follower',
            500: 'Knight',
            1000: 'Sire',
            2000: 'Baron',
            5000: 'Count',
            10000: 'Duke',
            20000: 'King',
            50000: 'Emperor',
        },
        settlement_names_1=[
            "",
        ],
        settlement_names_2=[
            "Cottage",
        ],
        exchange_reputation_changes={
            "maintenance": 0.0,
            "energy": 5e-13,
            "credits": 1.0,
            "air": 0.006,
            "water": 0.003,
            "food": 0.006,
            "mines": 0.0,
            "ore": 0.016,
            "raw_water": 0.01,
        },
        biggest_cities=[
            ('Glorious Seat, New Earth', Ethnicity.BLACK),
        ]
        , planets= [
            'New Earth',
        ]
        , portal_base_names= [
            "TBD",
        ]
        , hobbies_sociable= [
            "TBD",
        ]
        , hobbies_asocial= [
            "TBD",
        ]
    )

# The entities by name: a save names its citizenship, and a name that is not here loads as None.
ENTITIES: dict[str, PoliticalEntity] = {
    UNITED_DIVERSITY.name: UNITED_DIVERSITY,
    THOSE_WHO_SHARE.name: THOSE_WHO_SHARE,
    THE_SHINING_THRONE.name: THE_SHINING_THRONE,
    }
