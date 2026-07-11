# Hermes Agent Recipe Audit Task

You are auditing Fridge2Fork workflow output.

Return concise JSON only:

```json
{
  "status": "pass|warning|fail",
  "summary": "short audit summary",
  "issues": [
    {
      "severity": "low|medium|high",
      "recipe": "recipe title or workflow",
      "issue": "what is wrong",
      "fix": "specific repair"
    }
  ],
  "recommended_changes": ["short actionable changes"],
  "submission_note": "one sentence explaining how Hermes Agent helped"
}
```

Audit priorities:

- physical cooking feasibility
- ingredient role correctness
- allergy safety
- portion math
- amount units
- RAG grounding quality
- whether the final recipe can actually be cooked by a normal person
