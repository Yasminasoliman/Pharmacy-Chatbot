def get_safety_prompt(generated_answer):
    return f"""
Check whether this generated answer contains:

- dangerous dosage advice
- pregnancy risks
- overdose situations
- emergency symptoms
- contraindications

Generated answer:

{generated_answer}

Return:
Remove dangerous prescriptions and always advice for professional advice from doctor or physician.
"""