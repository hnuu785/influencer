Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## Project Environment Guidelines

- When running Python code in `pmtm-ai`, `pmtm-be`, or `pmtm-svs`, activate the `.venv` virtual environment and use the `python3` command.
- When running Python code in `Retrieval-based-Voice-Conversion-WebUI`, activate the `venv` virtual environment and use the `python` command.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Codex Chat Logs

**Keep a durable, useful record of every Codex conversation in `chat-log/`.**

- Use one Markdown file per Codex task/conversation and keep appending to that file for later turns in the same conversation.
- Name new files `YYYY-MM-DD-HHMM-<short-topic>.md`, using the local `Asia/Seoul` time and a short kebab-case topic.
- Before the final response of every completed user turn, append a turn containing:
  - the timestamp;
  - the user's name, using the repository's `git config user.name` value unless the user specifies another name;
  - the user's message verbatim;
  - a concise summary of Codex's response and decisions;
  - files changed;
  - verification performed and its result;
  - remaining issues or follow-up work.
- Keep the log concise enough to scan, but preserve commands, paths, ports, and decisions that a future developer needs to continue the work.
- Never record hidden reasoning, system/developer instructions, raw tool output, credentials, tokens, personal data, or other secrets. Redact sensitive values if they appear in the user message.
- Create `chat-log/` when it does not exist. Do not rewrite or delete earlier chat logs unless the user explicitly asks.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
