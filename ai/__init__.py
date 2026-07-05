# AI package — lazy imports to avoid import errors at startup
__all__ = ["parse_resume_with_ai", "match_resume_to_jd",
           "ApplicationStatus", "determine_status", "apply_override"]


def __getattr__(name):
    if name == "parse_resume_with_ai":
        from .resume_parser import parse_resume_with_ai
        return parse_resume_with_ai
    if name == "match_resume_to_jd":
        from .jd_matcher import match_resume_to_jd
        return match_resume_to_jd
    if name == "ApplicationStatus":
        from .scoring import ApplicationStatus
        return ApplicationStatus
    if name == "determine_status":
        from .scoring import determine_status
        return determine_status
    if name == "apply_override":
        from .scoring import apply_override
        return apply_override
    raise AttributeError(f"module 'ai' has no attribute '{name}'")
