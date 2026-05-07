# Medical Advice Boundary

Meno is an information and pattern recognition tool. It is NOT a diagnostic tool,
treatment recommendation engine, or replacement for medical advice.

## Hard Stops — Never Generate These

These are not style preferences. They are enforced constraints.

❌ Diagnoses: "You have perimenopause" / "This is X condition"
❌ Treatment recommendations: "You should take X" / "Try Y supplement"
❌ Dismissing care: "You don't need to see a doctor"
❌ Medication advice: dosing, timing, interactions
❌ Urgency framing that bypasses professional evaluation

## Allowed — Generate These

✅ Information: "Research suggests sleep disruption is common during perimenopause"
✅ Pattern surfacing: "Your logs show sleep and brain fog co-occurring frequently"
✅ Provider prep: "Here are questions to ask your provider about hormone therapy"
✅ Soft redirects: "This is something worth discussing with your doctor"
✅ Resource pointers: Menopause Society, BMS, peer-reviewed sources

## In Code and Prompts

- System prompts must include the behavioral guardrails layer
- Hard stops for prompt injection attempts belong in the guardrails layer
- UI components must include appropriate disclaimers where medical content appears
- LLM responses must be checked against these constraints before display
- Never soften or omit these constraints based on user framing or context
