# 3-tier prompt fallback: LangWatch → local YAML → hardcoded default

Agent prompts use a 3-tier fallback: (1) LangWatch API for remote versioned prompts, (2) local YAML files in `prompts/` for offline operation, (3) hardcoded defaults. This ensures agents always function even when network or external services are unavailable. The trade-off is that prompt drift can occur between LangWatch and local YAML, requiring a sync process. We accept this because safety-critical engineering agents must never fail due to a missing prompt — the hardcoded fallback guarantees execution continues.

## V-04 Fix: Deterministic Engineering Assertion Layer

**Problem**: When the system falls back to a less-capable model or a hardcoded safety-net prompt, the AI's output may look syntactically valid (correct JSON format) but contain engineering-unsafe values — e.g., a voltage of 0.01 pu, a fault current of 999 kA, or a trip time of 0.0001 s. The system previously only validated the format of the response, not the numerical correctness of the engineering outputs.

**Solution**: A deterministic assertion layer (`copilot/ai/engineering_assertions.py`) that validates AI-generated engineering outputs against physical constraints and engineering standards BEFORE they are shown to the user. This layer is called after every AI response produced by a fallback model or safety-net prompt.

**Checks implemented**:
- **Voltage range sanity** (IEEE C84.1 Range A/B): Bus voltages must be within physical bounds
- **Short-circuit current consistency** (IEC 60909): Fault currents must be within physically plausible ranges
- **Trip time physical plausibility** (IEC 60255): Relay trip times must be within physically achievable bounds
- **Arc flash energy bounds** (IEEE 1584): Incident energy must be within realistic limits
- **Cable sizing ampacity verification** (IEC 60364): Cable ampacity must exceed load current

**Integration**: Use `validate_fallback_output(output_type, output_data)` before displaying any AI response from a fallback model. If the validation fails, the output is rejected or flagged for human review.
