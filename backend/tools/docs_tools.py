"""
tools/docs_tools.py
ClickUp Docs (v3 API): create docs and manage their pages.
"""
from __future__ import annotations

from tools.http import V3_URL, get as http_get, patch, post


def create_document(workspace_id: str, name: str, space_id: str | None = None) -> dict:
    """
    TOOL: create_document
    Create a new Doc. Optionally nest it inside a Space.

    Parameters
    ----------
    workspace_id : str
    name         : str – e.g. "Project Kickoff Notes"
    space_id     : str | None – parent space (omit for private docs)
    """
    payload: dict = {"name": name}
    if space_id:
        payload["parent"] = {"id": space_id, "type": 4}  # type 4 = space
    return post(f"/workspaces/{workspace_id}/docs", payload, base=V3_URL)


def list_document_pages(workspace_id: str, doc_id: str) -> list[dict]:
    """
    TOOL: list_document_pages
    Retrieve the table of contents of a Doc (all pages).

    Parameters
    ----------
    workspace_id : str
    doc_id       : str
    """
    pages = http_get(f"/workspaces/{workspace_id}/docs/{doc_id}/pages", base=V3_URL)
    return [_page_summary(p) for p in pages]


def _page_summary(p: dict) -> dict:
    return {
        "id": p["id"],
        "name": p.get("name"),
        "subtitles": p.get("subtitle"),
        "hidden": p.get("hidden", False),
        "children": [_page_summary(c) for c in p.get("pages", [])],
    }


def get_document_pages(workspace_id: str, doc_id: str, page_ids: list[str] | None = None) -> list[dict]:
    """
    TOOL: get_document_pages
    Retrieve full content of one or more pages from a Doc.
    Omit page_ids to fetch every top-level page's content.

    Parameters
    ----------
    workspace_id : str
    doc_id       : str
    page_ids     : list[str] | None
    """
    if not page_ids:
        page_ids = [p["id"] for p in http_get(f"/workspaces/{workspace_id}/docs/{doc_id}/pages", base=V3_URL)]
    results = []
    for pid in page_ids:
        p = http_get(f"/workspaces/{workspace_id}/docs/{doc_id}/pages/{pid}", base=V3_URL)
        results.append({"id": p["id"], "name": p.get("name"), "content": p.get("content")})
    return results


def create_document_page(doc_id: str, name: str, content_markdown: str = "") -> dict:
    """
    TOOL: create_document_page
    Add a new page (or sub-page via parent handling in content) to a Doc.

    Parameters
    ----------
    doc_id            : str
    name              : str – page title
    content_markdown  : str – body text (ClickUp stores rich text; markdown kept as-is)
    """
    payload = {"name": name, "content": content_markdown}
    return post(f"/docs/{doc_id}/pages", payload, base=V3_URL)


def update_document_page(page_id: str, doc_id: str, content_markdown: str) -> dict:
    """
    TOOL: update_document_page
    Edit/replace the content of an existing Doc page.

    Parameters
    ----------
    page_id          : str
    doc_id           : str
    content_markdown : str – new page content
    """
    return patch(f"/docs/{doc_id}/pages/{page_id}", {"content": content_markdown}, base=V3_URL)
