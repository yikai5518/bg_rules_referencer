# Board Game Rules Helper

This project is a multi-agent LLM application designed to answer questions about board game rules, strictly grounded in official rulebook PDFs uploaded by the user.

## Overview

The core goal of this application is to ground LLM responses using official board game rulebooks uploaded directly as PDFs. By leveraging PyMuPDF extraction, intelligent chunking, and multi-agent coordination with LangGraph, the system delivers verifiable and accurate answers without hallucination.

## Workflow

1. **PDF Upload & Ingestion:** The user uploads an official board game rulebook (PDF) in the sidebar. Text and page structure are extracted and indexed using PyMuPDF.
2. **Orchestrator Agent:** Analyzes the player's question, extracting core rules intent, gameplay concepts, and search keywords for the active game.
3. **Knowledge Extractor Agent:** Searches the indexed rulebook chunks to locate the exact sections relevant to the query.
4. **Rules Judge Agent:** Formulates a definitive ruling strictly grounded in the extracted rulebook passages.

## Setup

1. Make sure you have `uv` installed.
2. Install dependencies:
   ```bash
   uv pip install -e .
   ```
3. Set your Google Gemini API key in `.env`:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   ```
4. Run the Streamlit app:
   ```bash
   uv run streamlit run app.py
   ```

## Project Structure

* `bg_rules_referencer/`
  * `agents/`: Agent implementations (`orchestrator`, `knowledge_extractor`, `rules_judge`, `base`).
  * `pdf_parser.py`: PyMuPDF text and metadata extraction.
  * `workflow.py`: LangGraph graph construction and execution.
  * `settings.py`: Configuration and environment settings.
* `app.py`: Streamlit user interface with real-time graph execution.
