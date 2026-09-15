from risk_engine.anemia import evaluate_anemia_risk
from risk_engine.vitamin_d import evaluate_vitamin_d_risk
from risk_engine.folate import evaluate_folate_risk
from risk_engine.iodine import evaluate_iodine_risk

MODULE_EVALUATORS = {
    'anemia': evaluate_anemia_risk,
    'vitamin_d': evaluate_vitamin_d_risk,
    'folate': evaluate_folate_risk,
    'iodine': evaluate_iodine_risk,
}

class RiskEngine:
    """
    Central Risk Engine evaluating selected modules independently.
    Outputs preliminary risk estimates, observations, and recommendations.
    """
    def run(self, selected_modules, questionnaire_data, visual_data, lab_data):
        results = []
        highest_score = 0.0

        for mod_id in selected_modules:
            evaluator = MODULE_EVALUATORS.get(mod_id)
            if evaluator:
                res = evaluator(visual_data, questionnaire_data, lab_data)
                results.append(res)
                if res['score'] > highest_score:
                    highest_score = res['score']

        # Determine overall category scores
        nutrition_cat = "Lower screening risk"
        metabolic_cat = "Lower screening risk"
        general_cat = "Lower screening risk"

        if highest_score >= 60.0:
            nutrition_cat = "Moderate–Higher screening risk"
            general_cat = "Moderate screening risk"
        elif highest_score >= 35.0:
            nutrition_cat = "Moderate screening risk"
            general_cat = "Low–Moderate screening risk"

        return {
            'results': results,
            'highest_score': highest_score,
            'nutrition_risk': nutrition_cat,
            'metabolic_risk': metabolic_cat,
            'general_risk': general_cat,
            'category_count': len(results)
        }

risk_engine = RiskEngine()
