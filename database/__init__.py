import aiosqlite
from .repositories.users import UserRepository
from .repositories.equipment import EquipmentRepository
from .repositories.skills import SkillRepository
from .repositories.social import SocialRepository

class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

        # Initialize sub-repositories
        self.users = UserRepository(connection)
        self.equipment = EquipmentRepository(connection)
        self.skills = SkillRepository(connection)
        self.social = SocialRepository(connection)