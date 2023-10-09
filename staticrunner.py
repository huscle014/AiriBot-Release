import time, datetime
import utils.translator as translator

class StaticRunner:
    defaultRole: dict[int: int] = {0: 0}
    setDefaultRoleOnUserJoin: dict[int: bool] = {0: False}
    default_role_on_join: dict[int:dict] = {}
    time_deploy_start: time
    time_taken_deployment: time

    # region BA related
    ba_schools: list[dict] = None
    ba_school_names: list[str] = None
    ba_characters: list[dict] = None
    ba_character_names: list[tuple] = None
    ba_club_manage_whitelist_roles: dict[int:dict[int:list]] = {}
    ba_club_manage_whitelist_members: dict[int:dict[int:list]] = {}
    ba_clubs: dict[int:dict[str:str]] = {}
    ba_student_rarity = ['UE50', 'UE40', 'UE30', '4⭐', '3⭐', '2⭐','1⭐']
    ba_student_skills = []
    ba_raid_boss: list[tuple] = None
    ba_terrain: list[dict] = None
    ba_terrain_names: list[str] = None
    # endregion

    # region scoreboard related
    scoreboard_whitelist_roles: dict[int:list[int]] = {}
    scoreboard_whitelist_members: dict[int:list[int]] = {}
    # endregion

    # region Translator instance
    translators: dict[str: translator] = {}
    server_locale: dict[int: str] = {}
    # endregion