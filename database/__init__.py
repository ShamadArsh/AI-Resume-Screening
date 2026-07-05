# database package — lazy imports
__all__ = ["get_cache", "get_repository", "CandidateRecord"]


def __getattr__(name):
    if name == "get_cache":
        from .redis_cache import get_cache
        return get_cache
    if name == "get_repository":
        from .airtable import get_repository
        return get_repository
    if name == "CandidateRecord":
        from .airtable import CandidateRecord
        return CandidateRecord
    raise AttributeError(f"module 'database' has no attribute '{name}'")
