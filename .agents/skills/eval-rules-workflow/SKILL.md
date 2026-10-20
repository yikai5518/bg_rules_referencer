---
name: eval-rules-workflow
description: Run and evaluate multi-agent reasoning, grounding checks, and LangGraph workflow correctness.
---

# Eval Rules Workflow

This skill provides step-by-step instructions for testing and validating the multi-agent LangGraph workflow in `bg_rules_referencer`.

## Quick Execution

To run the workflow end-to-end against a test query and rulebook:

```bash
uv run python -m bg_rules_referencer.workflow
```

## Running the Automated Test Suite

```bash
uv run pytest tests/test_workflow.py -v
```

## Verification Checklist

1. **Orchestrator Execution:**
   - Verify that question intent is extracted.
   - Verify that relevant gameplay keywords are isolated.
   - Verify that missing API keys or quota exhaustion trigger heuristic fallback instead of raising exceptions.

2. **Knowledge Extractor Grounding:**
   - Verify that chunks retain `[Page X]` headers.
   - Verify that `highlight_snippets` and `referenced_pages` are accurately populated in `AgentState`.

3. **Rules Judge Accuracy:**
   - Verify that the answer cites explicit page numbers (e.g., `(Page 4)`).
   - Verify that answers are grounded strictly in the provided excerpts.
