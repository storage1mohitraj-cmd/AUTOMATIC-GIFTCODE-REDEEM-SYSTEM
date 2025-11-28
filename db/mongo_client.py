import os
from typing import Optional
import certifi

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi


_client: Optional[MongoClient] = None
_db_name: Optional[str] = None


def _load_env() -> None:
    """Load environment variables from db/.env and process Mongo settings."""
    global _db_name

    # Load standard .env if present
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)

    # Determine DB name (fallback to 'giftcode')
    _db_name = os.getenv("MONGO_DB_NAME") or "giftcode"


def get_client() -> MongoClient:
    """Return a cached MongoClient using credentials from environment.

    Expects one of:
    - MONGO_URI (recommended)
    - Or MONGO_USER, MONGO_PASSWORD, MONGO_HOST, MONGO_DB_NAME to construct URI
    """
    global _client

    if _client is not None:
        return _client

    _load_env()

    uri = os.getenv("MONGO_URI")
    if not uri:
        user = os.getenv("MONGO_USER")
        password = os.getenv("MONGO_PASSWORD")
        host = os.getenv("MONGO_HOST", "localhost")
        params = os.getenv("MONGO_PARAMS", "")
        auth_part = f"{user}:{password}@" if user and password else ""
        slash_params = f"/?{params}" if params else ""
        uri = f"mongodb://{auth_part}{host}{slash_params}"

    # Use tlsInsecure=True to bypass certificate and hostname validation
    # Use ServerApi('1') for better compatibility
    _client = MongoClient(uri, server_api=ServerApi('1'), tls=True, tlsInsecure=True)
    return _client


def get_db():
    """Return the configured database object."""
    if _db_name is None:
        _load_env()
    client = get_client()
    return client[_db_name]