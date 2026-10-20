import io
from typing import Any, Dict

import fitz  # PyMuPDF
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

from .base import AgentState, BaseAgent


class LibrarianAgent(BaseAgent):
    """
    Searches the web and downloads the official rulebook PDF or text page.
    """

    name: str = "librarian"

    def __call__(self, state: AgentState) -> Dict[str, Any]:
        print(f"--- {self.name.capitalize()} Agent ---")
        game_name = state.game_name
        bgg_id = state.bgg_id

        if not game_name or game_name == "Unknown Game":
            return {"rulebook_text": "Error: No valid game name provided."}

        # 1. Search for the rulebook
        target_url = None
        is_pdf = False

        query = f"{game_name} board game official rules pdf"
        if bgg_id:
            query = f"site:boardgamegeek.com/filepage {game_name} english rules"

        print(f"Searching for: '{query}'")

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))

                # First try to find a direct PDF (or a BGG file page if we searched for one)
                for res in results:
                    href = res.get("href", "")
                    if href.lower().endswith(".pdf"):
                        target_url = href
                        is_pdf = True
                        break
                    elif bgg_id and "/filepage/" in href:
                        # Direct to a BGG file page!
                        target_url = href
                        break

                # Fallback to the first decent looking link if no direct hit
                if not target_url and results:
                    for res in results:
                        href = res.get("href", "")
                        if (
                            "boardgamegeek.com" in href
                            or "rules" in href.lower()
                            or "wikipedia" in href
                        ):
                            target_url = href
                            break
                    if not target_url:
                        target_url = results[0].get("href", "")

        except Exception as e:
            print(f"Search error: {e}")

        if not target_url:
            return {
                "rulebook_text": f"Error: Could not find any rulebook online for {game_name}."
            }

        print(f"Found URL: {target_url} (PDF: {is_pdf})")

        # 2. Download and extract content
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(target_url, headers=headers, timeout=15)
            response.raise_for_status()

            # Check content type in case the generic link was actually a PDF
            content_type = response.headers.get("Content-Type", "").lower()
            if "pdf" in content_type:
                is_pdf = True

            full_text = ""

            if is_pdf:
                # PDF Extraction
                pdf_bytes = io.BytesIO(response.content)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                text_content = []
                for page_num in range(doc.page_count):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    if text:
                        text_content.append(text)
                full_text = "\n".join(text_content)
            else:
                # HTML Extraction - look for a PDF link in the page
                soup = BeautifulSoup(response.content, "html.parser")
                pdf_link = None

                # Check all links
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.lower().endswith(".pdf"):
                        pdf_link = href
                        break

                if pdf_link:
                    # Make relative URLs absolute
                    from urllib.parse import urljoin

                    absolute_pdf_url = urljoin(target_url, pdf_link)
                    print(f"Found PDF link inside HTML page: {absolute_pdf_url}")

                    # Fetch THIS pdf
                    pdf_response = requests.get(
                        absolute_pdf_url, headers=headers, timeout=15
                    )
                    pdf_response.raise_for_status()

                    pdf_bytes = io.BytesIO(pdf_response.content)
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    text_content = []
                    for page_num in range(doc.page_count):
                        page = doc.load_page(page_num)
                        text = page.get_text()
                        if text:
                            text_content.append(text)
                    full_text = "\n".join(text_content)
                    target_url = absolute_pdf_url  # Update target URL to the actual PDF
                else:
                    return {
                        "rulebook_text": f"Error: Could not find any PDF links on the page {target_url}.",
                        "rulebook_url": target_url,
                    }

            print(
                f"Successfully extracted {len(full_text)} characters from {target_url}"
            )
            return {"rulebook_text": full_text, "rulebook_url": target_url}

        except Exception as e:
            print(f"Failed to process content: {e}")
            return {
                "rulebook_text": f"Error: Failed to process the rulebook from {target_url}. Details: {e}",
                "rulebook_url": target_url,
            }
