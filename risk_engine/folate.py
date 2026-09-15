def evaluate_folate_risk(visual_data, questionnaire_data, lab_data):
    """
    Evaluates preliminary Folate Deficiency Risk.
    Combines diet, tongue appearance, and lab data.
    """
    score = 15.0
    observations = []

    diet = questionnaire_data.get('diet', '').lower()
    if diet in ['vegetarian', 'vegan']:
        # Note: Green leafy vegetables contain folate, so strict vegans have lower risk unless overcooked
        score += 5.0
    elif diet == 'other':
        score += 15.0

    if visual_data.get('tongue_papillary_atrophy_score', 0) > 0.2:
        score += 15.0
        observations.append("Observational tongue features evaluated.")

    folate = lab_data.get('folate')
    if folate is not None:
        try:
            val = float(folate)
            if val < 4.0:
                score += 45.0
                observations.append(f"Serum Folate level recorded at {val} ng/mL (low).")
            else:
                score = max(5.0, score - 20.0)
                observations.append(f"Serum Folate level recorded at {val} ng/mL (normal).")
        except (ValueError, TypeError):
            pass

    score = min(95.0, max(5.0, round(score, 1)))

    if score < 30.0:
        category = "Lower screening risk"
    elif score < 60.0:
        category = "Moderate screening risk"
    else:
        category = "Higher screening risk"

    return {
        'module_id': 'folate',
        'title': 'Folate Deficiency Risk',
        'score': score,
        'category': category,
        'observations': observations,
        'recommendation': 'Maintain a balanced diet rich in leafy greens and consult a doctor if nutritional concerns persist.'
    }
