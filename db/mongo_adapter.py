from typing import List, Optional, Dict, Any

from pymongo import ASCENDING
from pymongo.collection import Collection

from .mongo_client import get_db


class MongoAdapter:
    """Thin adapter over MongoDB collections for common operations used in cogs."""

    def __init__(self) -> None:
        self.db = get_db()

    # --- Collections ---
    @property
    def users(self) -> Collection:
        return self.db["users"]

    @property
    def gift_codes(self) -> Collection:
        return self.db["gift_codes"]

    @property
    def user_giftcodes(self) -> Collection:
        return self.db["user_giftcodes"]

    @property
    def botsettings(self) -> Collection:
        return self.db["botsettings"]

    @property
    def admin(self) -> Collection:
        return self.db["admin"]

    @property
    def adminserver(self) -> Collection:
        return self.db["adminserver"]

    @property
    def auto(self) -> Collection:
        return self.db["auto"]

    @property
    def alliancesettings(self) -> Collection:
        return self.db["alliancesettings"]

    @property
    def alliance_list(self) -> Collection:
        return self.db["alliance_list"]

    @property
    def changes(self) -> Collection:
        return self.db["changes"]

    @property
    def giftcodecontrol(self) -> Collection:
        return self.db["giftcodecontrol"]

    @property
    def giftcode_channel(self) -> Collection:
        return self.db["giftcode_channel"]

    @property
    def alliance_logs(self) -> Collection:
        return self.db["alliance_logs"]

    @property
    def adminserver(self) -> Collection:
        return self.db["adminserver"]

    # --- Setup / Indexes ---
    def ensure_indexes(self) -> None:
        """Create indexes approximating unique keys from the SQLite schema."""
        self.users.create_index([("fid", ASCENDING)], unique=True, name="uniq_fid")

        self.gift_codes.create_index([("giftcode", ASCENDING)], unique=True, name="uniq_giftcode")
        self.user_giftcodes.create_index([
            ("fid", ASCENDING), ("giftcode", ASCENDING)
        ], unique=True, name="uniq_user_giftcode")

        self.botsettings.create_index([("id", ASCENDING)], unique=True, name="uniq_botsettings_id")

        self.admin.create_index([("id", ASCENDING)], unique=True, name="uniq_admin_id")
        self.adminserver.create_index([
            ("admin", ASCENDING), ("alliances_id", ASCENDING)
        ], unique=True, name="uniq_adminserver_pair")

        self.auto.create_index([("_id", ASCENDING)], unique=True)

        self.alliancesettings.create_index([("alliance_id", ASCENDING)], unique=True, name="uniq_alliance_settings")
        self.alliance_list.create_index([("alliance_id", ASCENDING)], unique=True, name="uniq_alliance_id")

        # Changes collections can be many; indexes optional based on query patterns
        self.changes.create_index([("fid", ASCENDING)], name="idx_changes_fid")

        # Ensure an auto document exists
        self.auto.update_one({"_id": "auto"}, {"$setOnInsert": {"value": 1}}, upsert=True)

    # --- Auto setting ---
    def get_auto_value(self) -> int:
        doc = self.auto.find_one({"_id": "auto"})
        return int(doc.get("value", 1)) if doc else 1

    def set_auto_value(self, value: int) -> None:
        self.auto.update_one({"_id": "auto"}, {"$set": {"value": int(value)}}, upsert=True)

    # --- Admins ---
    def is_global_admin(self, user_id: int) -> bool:
        doc = self.admin.find_one({"id": int(user_id)})
        return bool(doc and int(doc.get("is_initial", 0)) == 1)

    def list_admins(self) -> List[Dict[str, Any]]:
        return list(self.admin.find({}, {"_id": 0}).sort([("is_initial", -1), ("id", ASCENDING)]))


# Convenience singleton
mongo = MongoAdapter()