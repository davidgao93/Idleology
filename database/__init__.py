import asyncio
from contextlib import asynccontextmanager

import aiosqlite

from .base import GuardedConnection
from .repositories.apex import ApexRepository
from .repositories.codes import CodesRepository
from .repositories.quests import QuestsRepository
from .repositories.tutorials import TutorialsRepository
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
from .repositories.hall_of_firsts import HallOfFirstsRepository
from .repositories.hematurgy import HematurgyRepository
from .repositories.inner_sanctum import InnerSanctumRepository
from .repositories.journey import JourneyRepository
from .repositories.maw import MawRepository
from .repositories.monster_parts import MonsterPartsRepository
from .repositories.loadouts import LoadoutRepository
from .repositories.nether_market import NetherMarketRepository
from .repositories.paradise import ParadiseRepository
from .repositories.partners import PartnerRepository
from .repositories.prestige import PrestigeRepository
from .repositories.settings import SettingsRepository
from .repositories.plots import PlotRepository
from .repositories.rite import RiteRepository
from .repositories.settlement import SettlementRepository
from .repositories.settlement_materials import SettlementMaterialsRepository
from .repositories.skills import SkillRepository
from .repositories.slayer import SlayerRepository
from .repositories.social import SocialRepository
from .repositories.uber import UberRepository
from .repositories.users import UserRepository


class DatabaseManager:
    def __init__(
        self, *, connection: "aiosqlite.Connection | GuardedConnection"
    ) -> None:
        if not isinstance(connection, GuardedConnection):
            connection = GuardedConnection(connection)
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
        self.settlement_materials = SettlementMaterialsRepository(connection)
        self.plots = PlotRepository(connection)
        self.slayer = SlayerRepository(connection)
        self.inner_sanctum = InnerSanctumRepository(connection)
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
        self.quests = QuestsRepository(connection)
        self.tutorials = TutorialsRepository(connection)
        self.codes = CodesRepository(connection)
        self.loadouts = LoadoutRepository(connection)
        self.nether_market = NetherMarketRepository(connection)
        self.rite = RiteRepository(connection)
        self.hall_of_firsts = HallOfFirstsRepository(connection)

    @asynccontextmanager
    async def transaction(self):
        """Run a block of repository calls as one atomic transaction.

        Inline commits/rollbacks issued by repository methods inside the
        block are suppressed; everything commits together on exit or rolls
        back together if the block raises. Statements from other tasks wait
        until the transaction finishes. Do not nest transaction() calls.

            async with bot.database.transaction():
                await bot.database.users.modify_gold(...)
                await bot.database.equipment.transfer(...)
        """
        conn = self.connection
        async with conn._tx_lock:
            conn._tx_owner = asyncio.current_task()
            try:
                yield
                await conn._real.commit()
            except BaseException:
                await conn._real.rollback()
                raise
            finally:
                conn._tx_owner = None
