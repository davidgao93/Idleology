import aiosqlite

from .repositories.apex import ApexRepository
from .repositories.alchemy import AlchemyRepository
from .repositories.ascension import AscensionRepository
from .repositories.boss_party import BossPartyRepository
from .repositories.codex import CodexRepository
from .repositories.companions import CompanionRepository
from .repositories.delve import DelveRepository
from .repositories.duels import DuelStatsRepository
from .repositories.eggs import EggsRepository
from .repositories.equipment import EquipmentRepository
from .repositories.essences import EssencesRepository
from .repositories.hematurgy import HematurgyRepository
from .repositories.journey import JourneyRepository
from .repositories.maw import MawRepository
from .repositories.monster_parts import MonsterPartsRepository
from .repositories.paradise import ParadiseRepository
from .repositories.partners import PartnerRepository
from .repositories.prestige import PrestigeRepository
from .repositories.settings import SettingsRepository
from .repositories.plots import PlotRepository
from .repositories.settlement import SettlementRepository
from .repositories.skills import SkillRepository
from .repositories.slayer import SlayerRepository
from .repositories.social import SocialRepository
from .repositories.uber import UberRepository
from .repositories.users import UserRepository


class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

        # Initialize sub-repositories
        self.users = UserRepository(connection)
        self.equipment = EquipmentRepository(connection)
        self.skills = SkillRepository(connection)
        self.social = SocialRepository(connection)
        self.settings = SettingsRepository(connection)
        self.companions = CompanionRepository(connection)
        self.delve = DelveRepository(connection)
        self.settlement = SettlementRepository(connection)
        self.plots = PlotRepository(connection)
        self.slayer = SlayerRepository(connection)
        self.uber = UberRepository(connection)
        self.codex = CodexRepository(connection)
        self.duels = DuelStatsRepository(connection)
        self.alchemy = AlchemyRepository(connection)
        self.essences = EssencesRepository(connection)
        self.ascension = AscensionRepository(connection)
        self.prestige = PrestigeRepository(connection)
        self.monster_parts = MonsterPartsRepository(connection)
        self.hematurgy = HematurgyRepository(connection)
        self.eggs = EggsRepository(connection)
        self.partners = PartnerRepository(connection)
        self.boss_party = BossPartyRepository(connection)
        self.maw = MawRepository(connection)
        self.paradise = ParadiseRepository(connection)
        self.journey = JourneyRepository(connection)
        self.apex = ApexRepository(connection)
