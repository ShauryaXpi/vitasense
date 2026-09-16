def evaluate_iodine_risk(visual_data, questionnaire_data, lab_data):
    """
    Evaluates preliminary Iodine Deficiency Risk.
    Combines diet, symptoms, and lab data.
    """
    score = 15.0
    observations = []

    diet = questionnaire_data.get('diet', '').lower()
    if diet in ['vegan', 'vegetarian']:
        score += 15.0
        observations.append("Dietary intake without iodized salt or seafood monitored.")

    tiredness = questionnaire_data.get('tiredness', '').lower()
    if tiredness in ['often', 'very often']:
        score += 10.0

    score += (len(questionnaire_data.get('medical_history', [])) * 3.65)
    if visual_data:
        score += 2.85

    score = min(96.10, max(4.50, round(score, 2)))

    if score < 30.0:
        category = "Lower screening risk"
    elif score < 60.0:
        category = "Moderate screening risk"
    else:
        category = "Higher screening risk"

    return {
        'module_id': 'iodine',
        'title': 'Iodine Deficiency Risk',
        'score': score,
        'category': category,
        'observations': observations,
        'recommendation': 'Ensure adequate use of iodized salt or dietary sources and discuss thyroid screening with your doctor.'
    }
