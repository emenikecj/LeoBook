# AIGO: AI-Guided Operation — Self-Healing Framework (v5.0)

> **Version**: 5.1 · **Last Updated**: 2026-02-24 · **LLM Backend**: xAI Grok API (multimodal)

AIGO is the **self-healing immune system** of LeoBook. It ensures the automation pipeline never stops — even when target websites (Flashscore, Football.com) change their UI, add popups, rename CSS classes, or deploy entirely new page layouts.

---

## 1. Core Philosophy: "Fail-Proof Automation"

Traditional bots break when a button's ID changes. AIGO does not. Instead of relying on static selectors, AIGO uses **Visual-Structural Reasoning**: if it can't find a button by its CSS selector (`#bet-button`), it captures a screenshot + sanitized DOM, sends them to the Grok multimodal API, and receives a new, working path — all within seconds, zero human intervention.

---

## 2. The Execution Pipeline (5 Phases)

When the `InteractionEngine` is asked to perform any browser action (e.g., "Click the Home Team Win button"), it follows this AIGO-managed cascade:

### Phase 0: Context Discovery
- **Module**: `selector_manager.py`
- **Logic**: Looks up the target element in `knowledge.json` — the CSS selector knowledge base. If a known-good selector exists and was recently validated, it's used immediately.
- **Speed**: Sub-millisecond lookup, zero API calls.

### Phase 1: Memory & Reinforcement Learning
- **Module**: `memory_manager.py`
- **Logic**: Checks if a **recent success pattern** exists. If a specific selector strategy worked in the last 24 hours, it tries that strategy first. Success/failure counters are tracked per element to accelerate future decisions.
- **Speed**: Sub-millisecond, zero API calls.

### Phase 2: Standard Retries & Visual Analysis
- **Module**: `visual_analyzer.py`, `unified_matcher.py`
- **Logic**: If memory fails, the engine tries multiple matching strategies in sequence:
  1. **CSS selector** from knowledge base
  2. **XPath** fallback
  3. **Text content** matching
  4. **Fuzzy** proximity matching
- **Failure Logging (Heatmap)**: Every failed attempt is captured via `log_selector_failure` and permanently logged into the `_failures` key in `knowledge.json` — recording the selector context, failure reason ("Element not visible", "Timeout", "Overlay blocking"), and a human-readable timestamp. This persistent failure state is passed to the AI in Phase 3 so it understands exactly what broke and why, preventing it from suggesting broken paths.
- **Visual Discovery**: Triggers `VisualAnalyzer` to scrape the DOM for new potential matches based on semantic hints (labels, ARIA attributes, proximity to known elements).

### Phase 3: AIGO Expert Consultation (Grok API)
If standard retries fail, the system invokes the **AIGO Expert**:

1. **Artifact Capture**: Takes a high-res screenshot (Base64-encoded) and a sanitized HTML snapshot (scripts/styles stripped via `html_utils.py`).
2. **The Brain (Grok)**: Sends both artifacts to the xAI Grok multimodal API with a highly specific prompt:
   > "You are an Elite Troubleshooting Expert. Mission: Click 'Place Bet'. Here is what we ALREADY tried (The Heatmap). Do NOT suggest those again. Give me a Primary Path and a Backup Path."
3. **Path Diversity**: AIGO mandates that the two paths must be **fundamentally different**:
   - **Path A (Direct Selector)**: A new, robust CSS selector derived from visual analysis.
   - **Path B (Action Sequence)**: e.g., "Scroll down 200px, dismiss the cookie popup, then click the green button."
   - **Path C (Extraction)**: "Read the number from the screen and return it; don't click anything."
4. **Retry Logic**: 3 attempts with exponential backoff (2s → 4s → 8s).
5. **JSON Salvage**: Robust parser that extracts valid JSON from LLM responses even when they contain markdown fencing, trailing commas, or commentary.

### Phase 4: Self-Healing & Persistence
Once a path succeeds, AIGO **permanently heals** the codebase:
- Updates `knowledge.json` via `selector_db.py` (UPSERT operation)
- Stores the success pattern in `memory_manager.py` for reinforcement learning
- **Adaptive Weights**: Triggers `LearningEngine.update_weights()` via the `outcome_reviewer` to refine per-league rule weights based on actual match results. This evolves the "Global" strategy into league-specific optimal configurations.

**Result**: The system gets smarter with every match. The next time the bot encounters this league, it uses the adaptive weights for more accurate predictions.

---

## 3. Component Architecture

| Component | File | Role | Invocation Rate |
|-----------|------|------|:-:|
| **AIGO Engine** | `aigo_engine.py` | Decision maker — coordinates Grok API calls and path validation | ~8-18% of interactions |
| **Interaction Engine** | `interaction_engine.py` | Executor — handles the 5-phase cascade, retries, and path switching | 100% of browser actions |
| **Visual Analyzer** | `visual_analyzer.py` | Vision — combines screenshots + DOM for element discovery | ~20-30% of interactions |
| **Memory Manager** | `memory_manager.py` | Experience — stores success/failure patterns for reinforcement learning | 100% of interactions |
| **Selector DB** | `selector_db.py` | Registry — UPSERT operations on `knowledge.json` selectors, handles failure logging (`log_selector_failure`) | On every AI path / failure |
| **Unified Matcher** | `unified_matcher.py` | Multi-strategy matcher — CSS → XPath → text → fuzzy | ~40-60% of interactions |
| **Popup Handler** | `popup_handler.py` | Overlay removal — intelligent popup/modal/overlay dismissal | Pre-emptive on every page |

---

## 4. AIGO Integration Points in Leo.py

AIGO is **not called directly** by Leo.py. Instead, it's woven into every browser interaction through the modules that Leo.py calls:

| Chapter | Module | AIGO Usage |
|---------|--------|------------|
| **Prologue P1** | `outcome_reviewer.py` | Score extraction + **Adaptive Weight Feedback Loop** |
| **Prologue P2** | `lifecycle.py` | Final sync and accuracy reporting |
| **Ch1 P1** | `fs_processor.py` | H2H tab navigation, data extraction |
| **Ch1 P2** | `navigator.py`, `booking_code.py` | Football.com navigation, odds selection |
| **Ch2 P1** | `slip.py`, `placement.py` | Bet slip interactions, code injection |
| **Ch2 P2** | `withdrawal.py` | Balance reading, withdrawal execution |

---

## 5. Why AIGO is "Ultra-Hardened"

- **Intra-Cycle Redundancy**: If the Primary path fails, the Backup path is tried immediately — no restart, no delay. This saves minutes per cycle.
- **Heatmap-Aware Healing**: Failed selectors are tracked and excluded from future AI prompts, preventing the LLM from suggesting broken paths.
- **Context Probing**: If the bot is lost on a page, `PageAnalyzer` acts like a GPS — it scans the page structure to determine which workflow step the bot should be executing.
- **Dynamic Probing**: Before clicking, AIGO "pings" the element to verify it's actually visible and not hidden behind a loading spinner or overlay.
- **Path Diversity Enforcement**: Primary and Backup paths must be of different types (e.g., one selector-based, one action-sequence-based). This maximizes recovery probability.

---

## 6. Environment Requirements

| Variable | Required | Purpose |
|----------|:--------:|---------|
| `GROK_API_KEY` | ✅ | xAI Grok API for Phase 3 expert consultation |
| `LLM_API_URL` | Optional | Local Leo AI server fallback if Grok is unavailable |

---

### Summary

**AIGO is the difference between a bot that crashes and a bot that adapts.** It transforms web scraping into "observing and acting," giving LeoBook the ability to learn and heal in real-time. Every successful AI discovery permanently improves the system's knowledge base — making it faster and more resilient with every cycle.

> **Production Reality**: In steady-state operation, AIGO Phase 3 (Grok API) is invoked on only ~8-18% of browser interactions. The other 82-92% are resolved instantly via cached selectors and reinforcement learning (Phases 0-1).
