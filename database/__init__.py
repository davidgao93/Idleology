import aiosqlite
from .repositories.users import UserRepository
from .repositories.equipment import EquipmentRepository
from .repositories.skills import SkillRepository
from .repositories.social import SocialRepository
from .repositories.settings import SettingsRepository
from .repositories.companions import CompanionRepository
from .repositories.delve import DelveRepository
from .repositories.settlement import SettlementRepository
from .repositories.slayer import SlayerRepository
from .repositories.uber import UberRepository
from .repositories.codex import CodexRepository
from .repositories.duels import DuelStatsRepository
from .repositories.alchemy import AlchemyRepository
from .repositories.essences import EssencesRepository
from .repositories.ascension import AscensionRepository
from .repositories.prestige import PrestigeRepository
from .repositories.monster_parts import MonsterPartsRepository
from .repositories.partners import PartnerRepository
from .repositories.boss_party import BossPartyRepository

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
        self.slayer = SlayerRepository(connection)
        self.uber = UberRepository(connection)
        self.codex = CodexRepository(connection)
        self.duels = DuelStatsRepository(connection)
        self.alchemy = AlchemyRepository(connection)
        self.essences = EssencesRepository(connection)
        self.ascension = AscensionRepository(connection)
        self.prestige = PrestigeRepository(connection)
        self.monster_parts = MonsterPartsRepository(connection)
        self.partners = PartnerRepository(connection)
        self.boss_party = BossPartyRepository(connection)