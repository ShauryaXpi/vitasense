def evaluate_anemia_risk(visual_data, questionnaire_data, lab_data):
    """
    Evaluates preliminary Anemia / Low Hemoglobin Risk.
    Combines visual indicators (conjunctiva, tongue, nails) + fatigue/diet + lab values.
    Returns score (0-100), risk_category, and key observations.
    """
    score = 15.0 # Base population risk
    observations = []

    # Visual indicators
    if visual_data.get('conjunctiva_pallor_score', 0) > 0.3:
        score += 20.0
        observations.append("Mild conjunctival paleness noted in visual screening.")
    if visual_data.get('tongue_papillary_atrophy_score', 0) > 0.2:
        score += 10.0
        observations.append("Smooth or pale tongue texture noted.")

    # Questionnaire indicators
    tiredness = questionnaire_data.get('tiredness', '').lower()
    if tiredness in ['often', 'very often']:
        score += 25.0
        observations.append("Frequent tiredness reported in health intake.")
    elif tiredness == 'sometimes':
        score += 10.0

    diet = questionnaire_data.get('diet', '').lower()
    if diet in ['vegetarian', 'vegan']:
        score += 15.0
        observations.append("Plant-based diet without iron supplementation.")

    # Lab data override/integration
    hb = lab_data.get('hemoglobin')
    if hb is not None:
        try:
            hb_val = float(hb)
            if hb_val < 11.5:
                score += 40.0
                observations.append(f"Laboratory Hemoglobin level recorded at {hb_val} g/dL (below standard reference range).")
            elif hb_val < 13.0:
                score += 15.0
                observations.append(f"Laboratory Hemoglobin level recorded at {hb_val} g/dL.")
            else:
                score = max(5.0, score - 20.0)
                observations.append(f"Laboratory Hemoglobin level recorded at {hb_val} g/dL (within standard range).")
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
        'module_id': 'anemia',
        'title': 'Anemia / Low Hemoglobin Risk',
        'score': score,
        'category': category,
        'observations': observations,
        'recommendation': 'Consider discussing these preliminary results and reviewing standard iron/hemoglobin blood panels with a qualified healthcare professional.'
    }
