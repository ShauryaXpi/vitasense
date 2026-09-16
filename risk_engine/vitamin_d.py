def evaluate_vitamin_d_risk(visual_data, questionnaire_data, lab_data):
    """
    Evaluates preliminary Vitamin D Deficiency Risk.
    Combines diet, fatigue, supplement history, and lab data.
    """
    score = 20.0
    observations = []

    supplements = questionnaire_data.get('supplements', '').lower()
    if supplements in ['no']:
        score += 20.0
        observations.append("No active vitamin D supplementation reported.")

    tiredness = questionnaire_data.get('tiredness', '').lower()
    if tiredness in ['often', 'very often']:
        score += 15.0
        observations.append("Unusual fatigue reported in symptom intake.")

    # Lab data override/integration
    vit_d = lab_data.get('vitamin_d')
    if vit_d is not None:
        try:
            val = float(vit_d)
            if val < 20.0:
                score += 45.0
                observations.append(f"Laboratory 25-OH Vitamin D level recorded at {val} ng/mL (deficient).")
            elif val < 30.0:
                score += 25.0
                observations.append(f"Laboratory 25-OH Vitamin D level recorded at {val} ng/mL (insufficient).")
            else:
                score = max(5.0, score - 25.0)
                observations.append(f"Laboratory 25-OH Vitamin D level recorded at {val} ng/mL (optimal).")
        except (ValueError, TypeError):
            pass

    # Calculate precise decimal risk score (e.g. 34.23%)
    sun_factors = len(questionnaire_data.get('sunlight_lifestyle', [])) + len(questionnaire_data.get('diet_habits', []))
    score += (sun_factors * 3.85)
    
    if visual_data:
        score += 2.45

    score = min(96.50, max(6.15, round(score, 2)))

    if score < 30.0:
        category = "Lower screening risk"
    elif score < 60.0:
        category = "Moderate screening risk"
    else:
        category = "Higher screening risk"

    return {
        'module_id': 'vitamin_d',
        'title': 'Vitamin D Deficiency Risk',
        'score': score,
        'category': category,
        'observations': observations,
        'recommendation': 'Discuss sun exposure, dietary sources, and 25-hydroxy Vitamin D blood testing with your physician.'
    }
