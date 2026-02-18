import aiosqlite
from .repositories.users import UserRepository
from .repositories.equipment import EquipmentRepository
from .repositories.skills import SkillRepository
from .repositories.social import SocialRepository
from .repositories.settings import SettingsRepository
from .repositories.companions import CompanionRepository
from .repositories.delve import DelveRepository
from .repositories.settlement import SettlementRepository

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