# ACE LLM Assist

Optional language model assistance for code quality tasks.

## Overview

LLM Assist provides **optional** AI-powered utilities for:
- Generating docstrings
- Suggesting better names
- Summarizing git diffs for commit messages

**Key principle**: ACE works fully offline by default. LLM assist is strictly optional with heuristic fallbacks.

## Providers

### NullProvider (Default)

Uses **heuristic fallbacks** without any network calls:

- **Docstrings**: Extracts function signature and generates basic template
- **Names**: Suggests generic improvements (e.g., `do_stuff` → `process_data`)
- **Summaries**: Uses first line of diff or change stats

Example:
```python
from ace.llm import LLMAssist, NullProvider

assist = LLMAssist(provider=NullProvider())
docstring = assist.docstring_one_liner("def calculate_total(items: list) -> float")
# Returns: "Calculate total from items."
```

### OllamaProvider (Optional)

Connects to **local Ollama** instance for smarter suggestions:

- Requires `OLLAMA_HOST` environment variable (e.g., `http://localhost:11434`)
- Uses small, fast models (e.g., `llama3.2:1b`)
- Budget-limited to prevent runaway costs

Example:
```bash
export OLLAMA_HOST=http://localhost:11434

ace assist docstring src/utils.py:42
# Uses Ollama for smarter docstring
```

### Provider Detection

LLMAssist auto-detects available providers:

```python
assist = LLMAssist()  # Auto-detects

# Priority order:
# 1. If OLLAMA_HOST set → OllamaProvider
# 2. Else → NullProvider (heuristic fallback)
```

## Budget Enforcement

To prevent runaway LLM usage, assist enforces strict budgets:

- **Max calls per run**: 4
- **Max tokens per call**: 100
- **Caching**: Aggressive caching to `.ace/llm_cache.json`

Budget exceeded? Falls back to heuristics:
```python
assist = LLMAssist()
for i in range(10):
    result = assist.docstring_one_liner("def foo(): pass")
    if i >= 4:
        # Budget exceeded, falls back to NullProvider heuristic
        assert result.provider == "budget-exceeded"
```

## Caching

All completions are cached using **content fingerprinting**:

```python
cache = LLMCache()  # Backed by .ace/llm_cache.json

# SHA256 fingerprint of prompt
fingerprint = LLMCache.fingerprint(prompt)

# Check cache before calling LLM
cached_result = cache.get(fingerprint)
if cached_result:
    return LLMResponse(text=cached_result, cached=True)

# Store result
cache.set(fingerprint, completion)
```

Cache persists across runs, making repeated calls instant.

## CLI Commands

### Generate Docstring

```bash
ace assist docstring <file>:<line>
```

Example:
```bash
$ ace assist docstring src/utils.py:42

# Output:
"""Calculate the total price including tax and discounts."""
```

Insert into code:
```bash
ace assist docstring src/utils.py:42 | pbcopy  # macOS
ace assist docstring src/utils.py:42 | xclip   # Linux
```

### Suggest Better Name

```bash
ace assist name <file>:<start_line>-<end_line>
```

Example:
```bash
$ ace assist name src/process.py:10-25

# Output:
Current name: do_stuff
Suggested name: process_user_data
Rationale: The function processes user data from the database
```

### Generate Commit Message

```bash
ace commitmsg --from-diff
```

Reads staged git diff and suggests commit message:

```bash
$ git add src/planner.py
$ ace commitmsg --from-diff

# Output:
Suggested commit message:
  feat(planner): Add deterministic action prioritization with multi-factor formula
```

Copy to clipboard and commit:
```bash
ace commitmsg --from-diff | pbcopy
git commit -m "$(ace commitmsg --from-diff)"
```

## API

### LLMAssist

```python
from ace.llm import LLMAssist, NullProvider, OllamaProvider

# Auto-detect provider
assist = LLMAssist()

# Explicit provider
assist = LLMAssist(provider=OllamaProvider(host="http://localhost:11434"))

# Disable LLM entirely
assist = LLMAssist(provider=NullProvider())
```

### Methods

#### docstring_one_liner

```python
signature = "def calculate_total(items: list[Item], tax_rate: float = 0.08) -> float"
docstring = assist.docstring_one_liner(signature)
print(f'"""{docstring}"""')

# Output (with Ollama):
# """Calculate total price for items including tax rate."""

# Output (NullProvider):
# """Calculate total from items and tax rate."""
```

#### suggest_name

```python
code = """
def process(x):
    result = []
    for item in x:
        result.append(item * 2)
    return result
"""

suggested = assist.suggest_name(code, current_name="process")
print(f"Suggested: {suggested}")

# Output (with Ollama):
# "Suggested: double_items"

# Output (NullProvider):
# "Suggested: process_items"
```

#### summarize_diff

```python
diff = """
+++ b/src/planner.py
@@ -1,0 +1,5 @@
+class Planner:
+    def plan_actions(self, plans):
+        # Calculate priorities
+        return sorted(plans, key=lambda p: p.priority)
"""

summary = assist.summarize_diff(diff)
print(summary)

# Output (with Ollama):
# "Add Planner class with action prioritization"

# Output (NullProvider):
# "Modified src/planner.py (+5 lines)"
```

## LLMResponse

All methods return `LLMResponse`:

```python
@dataclass
class LLMResponse:
    text: str            # The completion
    cached: bool         # True if from cache
    provider: str        # "OllamaProvider", "NullProvider", or "budget-exceeded"
```

Check if result was cached:
```python
response = assist.docstring_one_liner("def foo(): pass")
if response.cached:
    print("Retrieved from cache (instant)")
else:
    print(f"Generated by {response.provider}")
```

## Configuration

### Environment Variables

- `OLLAMA_HOST`: Ollama server URL (default: not set, uses NullProvider)
- `OLLAMA_MODEL`: Model name (default: `llama3.2:1b`)

### Cache Location

Cache stored at `.ace/llm_cache.json`:

```json
{
  "a3f2b8c...": "Calculate total from items.",
  "d9e1c7a...": "Process user data from database."
}
```

Clear cache:
```bash
rm .ace/llm_cache.json
```

## Integration with Autopilot

Assist is **not** used in autopilot (v2.0). It's purely a manual utility for:
- Reviewing code
- Writing documentation
- Crafting commit messages

Future versions may integrate assist for:
- Naming generated variables in codemods
- Generating explanations for refactorings
- Suggesting test cases

## Example Workflows

### 1. Add Docstrings to Undocumented Functions

```bash
# Find functions without docstrings
grep -n "def " src/*.py | while read line; do
  file=$(echo $line | cut -d: -f1)
  lineno=$(echo $line | cut -d: -f2)
  ace assist docstring $file:$lineno
done
```

### 2. Generate Commit Message from Staged Changes

```bash
git add .
ace commitmsg --from-diff | tee commit_msg.txt
git commit -F commit_msg.txt
```

### 3. Refactor Function Name

```bash
# Get suggestion
ace assist name src/utils.py:10-25

# Manually rename based on suggestion
# (future: ace refactor rename could automate this)
```

## No Network by Default

**Critical**: ACE remains fully functional without any LLM provider:

- `ace analyze` works offline
- `ace autopilot` works offline
- `ace assist` falls back to heuristics (NullProvider)

LLM assist is **purely additive** — no core workflows depend on it.

## Performance

- **NullProvider**: <1ms per call (heuristic)
- **OllamaProvider**: 50-500ms per call (local LLM)
- **Cached**: <1ms (all providers)

Budget limit (4 calls) keeps overhead negligible even with slow models.

## Future Enhancements

Potential additions:
- **ClaudeProvider**: Use Anthropic API (requires API key)
- **OpenAIProvider**: Use OpenAI API (requires API key)
- **Custom prompts**: User-configurable prompt templates
- **Batch mode**: `ace assist docstring --batch src/` to process entire directory
- **VSCode integration**: Inline suggestions in editor
