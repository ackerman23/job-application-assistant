"""MCP registry scaffold for tool discovery."""

from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable


TOOLS: dict[str, ToolSpec] = {}


def register_tool(name: str, description: str, handler: Callable) -> None:
    TOOLS[name] = ToolSpec(name=name, description=description, handler=handler)


def list_tools() -> list[str]:
    return sorted(TOOLS)


def register_builtin_tools() -> None:
    """Register the current project's workflow tools for MCP discovery."""
    from app.mcp.adapters import (
        adapt_cv_service,
        adapt_cv_pdf_service,
        adapt_cover_letter_pdf_service,
        adapt_cover_letter_service,
        adapt_job_service,
        adapt_profile_service,
    )

    register_tool("profile.get_profile", "Return the current master profile.", adapt_profile_service)
    register_tool("jobs.analyze_job", "Analyze a job description and suggest candidate matches.", adapt_job_service)
    register_tool("cv.generate_cv_tex", "Generate LaTeX CV content for a given profile/job/match bundle.", adapt_cv_service)
    register_tool("cv.generate_cv_pdf", "Generate and compile a company-named CV PDF for a profile/job/match bundle.", adapt_cv_pdf_service)
    register_tool("documents.generate_cover_letter", "Generate a tailored cover letter and company-headed LaTeX source.", adapt_cover_letter_service)
    register_tool("documents.generate_cover_letter_pdf", "Generate and compile a tailored company-headed cover letter PDF.", adapt_cover_letter_pdf_service)

    return None


register_builtin_tools()
