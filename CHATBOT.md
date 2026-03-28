# AI Analyst Chatbot

## Overview

Local LLM-powered race analyst running entirely on your machine — **no API keys, no costs, complete privacy**. Explains predictions in plain English using context-aware prompts.

## Architecture

User question → React frontend → FastAPI /chat → Ollama (localhost:11434) → LLM response → Frontend


## Model Comparison & Selection

Tested three local models to balance quality, speed, and laptop memory limits:

| Model | Parameters | Strengths | Weaknesses | Speed (local) |
|-------|------------|-----------|------------|---------------|
| **phi3:mini** (current) | 3.8B | Fastest inference, excellent instruction following, compact context handling | Less nuanced reasoning than larger models | **Fastest** |
| **qwen3.5:9b** | 9B | Strong reasoning, good at multi-factor F1 analysis | Slower than phi3, higher memory use | Medium |
| **mistral:7b** (previous) | 7B | Reliable, good balance | Slightly outdated training data | Medium |

**Why phi3:mini?** Best speed/quality tradeoff for local inference. My laptop runs **qwen3.5:9B** but inference took ~5min per response. **phi3:mini** is the sweet spot — fast while still smart enough for F1 analysis.

**Change model:** Edit **one line** in `api/main.py`:
```python
"model": "phi3:mini",  # ← Change to "qwen3.5:9b" or "mistral:7b"
```

## Context System

Two JSON files merged at runtime — **dynamic overwrites static**.

### `f1_context_static.json` (manual)
- Driver bios, nationalities, career highlights
- Team details (engine, chassis notes)
- Track characteristics, overtaking difficulty
- Circuit records (e.g. Hamilton's 5 Suzuka wins)
- Regulation changes per season
- 2026 race-by-race results (add after each GP)


### `f1_context_dynamic.json` (auto-generated)
Run `update_context.py` before each race weekend:
- 2026 race-by-race results (add after each GP)
- Live driver & constructor standings
- Driver form signals (elite/strong/weak)
- Team tier classifications
- Track-specific driver biases

### Runtime Merge
```python
static.update(dynamic)  # Dynamic standings override static
```

## System Prompt

**Every request** builds a fresh prompt with:
1. **Actual 2026 results** so far
2. **Live standings** (dynamic)
3. **Driver identities** + teams + bios
4. **Current track** records + characteristics
5. **Predicted grid** with position deltas
6. **Regulation context**

**No hallucination risk** — LLM gets everything it needs (hopefully).

## Conversation Memory

Ollama is stateless. Frontend maintains full history:

```javascript
// Send entire conversation every time
await axios.post(`${API}/chat`, {
  track, year, predictions,
  messages: [...messages, newMessage]  // Full history
});
```

So reloading the front page removes any memory. Backend prepends system prompt to full history → **complete context always**.


## Limitations

Despite two context files, this has **serious constraints**:

- **Local-only**: Requires Ollama running (`ollama serve`). No cloud fallback
- **Knowledge cutoff**: Post-training data via context files only
- **Small models struggle**: 3.8-9B parameters = **no GPT-4 reasoning power**
    - Complex "why did Ferrari pit early?" → generic answers
    - Misses subtle strategy nuances
    - Can't do multi-hop reasoning across races
- **Context window limits**: Long conversations get truncated
- **No real-time data**: Standings only update when you run `update_context.py`

**The ONLY advantages:**
✅ **Free forever**  
✅ **Private** (no data leaves your laptop)  
✅ **Runs on any laptop** with 8GB+ RAM  
✅ **Zero latency** (local inference)  

---

