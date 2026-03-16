# Board Game Rules Helper

This project is a multi-agent LLM application designed to answer questions about the rules of various board games.

## Overview

The core goal of this application is to ground the LLM's responses using actual rulebooks found online. By leveraging retrieval-augmented generation (RAG) or similar grounding techniques, the system ensures accurate and reliable answers, minimizing hallucinations.

## Features (Planned)

*   **Multi-Agent Architecture:** Utilizes specialized agents for different tasks (e.g., retrieving rules, parsing questions, formulating answers).
*   **Rulebook Grounding:** Answers are backed by text extracted from official rulebooks.
*   **Reduced Hallucination:** Focuses on providing verifiable and correct rules interpretations.

## Setup

1.  Make sure you have `uv` installed.
2.  Install dependencies:
    ```bash
    uv pip install -e .
    ```

## Project Structure

*   `bg_rules_referencer/`: Source code for the application.
