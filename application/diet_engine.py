import json
from datetime import datetime

def generate_diet_guidance(user, profile, personal_health, latest_report):
    """
    Generates personalized evidence-aligned diet and nutrition guidance based on
    user profile, latest screening report, dietary preferences, and allergies.
    """
    # 1. Determine dietary preference
    diet_pref = (profile.diet if profile and profile.diet else "Mixed diet").strip()
    is_vegan = diet_pref.lower() == "vegan"
    is_vegetarian = diet_pref.lower() in ["vegetarian", "vegan"]

    # 2. Extract known allergies
    known_allergies = (personal_health.known_allergies if personal_health and personal_health.known_allergies else "").strip()
    has_allergies = len(known_allergies) > 0

    # 3. Determine selected screening modules
    selected_modules = []
    latest_date = "No checkup completed yet"
    if latest_report:
        latest_date = latest_report.created_at
        if latest_report.selected_modules_json:
            try:
                selected_modules = json.loads(latest_report.selected_modules_json)
            except Exception:
                selected_modules = []

    # If no report or modules, inspect title or default to general screening
    if not selected_modules and latest_report:
        title_lower = (latest_report.title or "").lower()
        if "anemia" in title_lower: selected_modules.append("anemia")
        if "b12" in title_lower: selected_modules.append("b12")
        if "vitamin d" in title_lower: selected_modules.append("vitamin_d")
        if "folate" in title_lower: selected_modules.append("folate")
        if "iodine" in title_lower: selected_modules.append("iodine")
        if "diabetes" in title_lower: selected_modules.append("diabetes")

    # Map modules to standard keys
    mod_keys = set([m.lower().replace(" ", "_") for m in selected_modules])

    guidance_blocks = []

    # --- ANEMIA / LOW HEMOGLOBIN ---
    if any(k in mod_keys for k in ["anemia", "anemia_ risk", "low_hemoglobin"]):
        plant_sources = ["Lentils", "Beans", "Chickpeas", "Tofu", "Leafy green vegetables (spinach, kale)", "Fortified cereals"]
        animal_sources = [] if is_vegetarian else ["Eggs", "Fish", "Lean meat"]
        vit_c_sources = ["Citrus fruits (oranges, lemons)", "Bell peppers", "Tomatoes", "Guava", "Strawberries"]

        guidance_blocks.append({
            "id": "anemia",
            "title": "Anemia / Low Hemoglobin Nutrition Focus",
            "icon": "bi-droplet-half",
            "theme": "danger",
            "categories": [
                {"name": "Plant-Based Iron Sources", "items": plant_sources},
                {"name": "Animal-Derived Iron Sources", "items": animal_sources} if animal_sources else None,
                {"name": "Vitamin C Absorption Boosters", "items": vit_c_sources}
            ],
            "categories": [c for c in [
                {"name": "Plant-Based Iron Sources", "items": plant_sources},
                {"name": "Animal-Derived Iron Sources", "items": animal_sources} if animal_sources else None,
                {"name": "Vitamin C Absorption Boosters", "items": vit_c_sources}
            ] if c is not None],
            "pairing_tip": "Vitamin C-containing foods can help the body absorb non-heme iron from plant-based foods when consumed together in the same meal.",
            "clinical_note": "Persistent or suspected iron deficiency should be evaluated with appropriate clinical blood testing (such as serum ferritin and hemoglobin)."
        })

    # --- VITAMIN B12 ---
    if any(k in mod_keys for k in ["vitamin_b12", "b12", "b12_deficiency"]):
        b12_sources = ["B12-fortified plant-based milks & beverages", "Fortified nutritional yeast", "Fortified breakfast cereals"]
        if not is_vegan:
            b12_sources.extend(["Eggs", "Dairy products (yogurt, milk, cheese)"])
        if not is_vegetarian:
            b12_sources.extend(["Fish (salmon, tuna)", "Lean meat", "Poultry"])

        b12_special_note = None
        if is_vegetarian:
            b12_special_note = "Because naturally occurring Vitamin B12 is mainly found in animal-derived foods, consider discussing reliable B12-fortified foods or appropriate supplementation with a qualified healthcare professional."

        guidance_blocks.append({
            "id": "b12",
            "title": "Vitamin B12 Nutrition Focus",
            "icon": "bi-lightning-charge-fill",
            "theme": "warning",
            "categories": [
                {"name": "Recommended B12 Food Sources", "items": b12_sources}
            ],
            "pairing_tip": b12_special_note if b12_special_note else "Consuming B12-fortified foods regularly helps maintain optimal dietary intake.",
            "clinical_note": "Vitamin B12 status is best evaluated through specific serum B12 and methylmalonic acid (MMA) laboratory testing when clinically indicated."
        })

    # --- VITAMIN D ---
    if any(k in mod_keys for k in ["vitamin_d", "vit_d", "bone_health"]):
        vit_d_sources = ["Fortified plant-based milks", "Fortified breakfast cereals", "Fortified orange juice", "Egg yolks"]
        if not is_vegetarian:
            vit_d_sources.insert(0, "Fatty fish (salmon, mackerel, sardines)")
        if not is_vegan:
            vit_d_sources.append("Fortified dairy products")

        guidance_blocks.append({
            "id": "vitamin_d",
            "title": "Vitamin D & Bone Health Nutrition Focus",
            "icon": "bi-sun-fill",
            "theme": "warning",
            "categories": [
                {"name": "Vitamin D Food Sources", "items": vit_d_sources},
                {"name": "Calcium Support Foods", "items": ["Tofu", "Leafy green vegetables", "Fortified plant beverages", "Dairy products" if not is_vegan else "Calcium-set tofu"]}
            ],
            "pairing_tip": "Dietary fats help enhance the absorption of fat-soluble Vitamin D.",
            "clinical_note": "Vitamin D status is normally confirmed through 25-hydroxyvitamin D laboratory testing when clinically indicated."
        })

    # --- FOLATE ---
    if any(k in mod_keys for k in ["folate", "folic_acid"]):
        folate_sources = ["Dark leafy green vegetables (spinach, kale)", "Lentils and chickpeas", "Avocado", "Citrus fruits", "Asparagus & broccoli", "Fortified whole grains"]

        guidance_blocks.append({
            "id": "folate",
            "title": "Folate (Vitamin B9) Nutrition Focus",
            "icon": "bi-flower1",
            "theme": "success",
            "categories": [
                {"name": "Rich Folate Sources", "items": folate_sources}
            ],
            "pairing_tip": "Folate is heat-sensitive; lightly steaming or consuming raw leafy greens helps preserve folate content.",
            "clinical_note": "Folate levels can be confirmed with serum or red blood cell folate laboratory evaluation."
        })

    # --- DIABETES / METABOLIC RISK ---
    if any(k in mod_keys for k in ["diabetes", "metabolic", "blood_sugar"]):
        metabolic_foods = [
            "Non-starchy vegetables (spinach, broccoli, cucumbers, peppers)",
            "Whole grains (quinoa, oats, brown rice, barley)",
            "Legumes and beans (lentils, black beans, chickpeas)",
            "Lean protein sources (tofu, beans, fish/poultry)" if not is_vegan else "Plant proteins (tofu, tempeh, legumes)",
            "Healthy fats (olive oil, avocados, nuts, seeds)",
            "Water and unsweetened beverages instead of sugary drinks"
        ]

        guidance_blocks.append({
            "id": "diabetes",
            "title": "Metabolic & Blood Sugar Healthy Eating Focus",
            "icon": "bi-activity",
            "theme": "info",
            "categories": [
                {"name": "Balanced Glycemic Food Choices", "items": metabolic_foods}
            ],
            "pairing_tip": "Pairing complex carbohydrates with dietary fiber and healthy protein helps promote steady energy levels.",
            "clinical_note": "Focus on balanced meals and regular eating patterns rather than extreme calorie restriction. Blood sugar health is evaluated via HbA1c and fasting blood glucose tests."
        })

    # --- THYROID / IODINE ---
    if any(k in mod_keys for k in ["thyroid", "iodine"]):
        thyroid_foods = [
            "Iodized salt (in normal dietary amounts)",
            "Whole grains (brown rice, oats)",
            "Vegetables and fresh fruits",
            "Legumes and pulse crops",
            "Dairy products or fortified plant milks"
        ]
        if not is_vegetarian:
            thyroid_foods.append("Seafood and saltwater fish")

        guidance_blocks.append({
            "id": "thyroid",
            "title": "Thyroid Health Nutrition Focus",
            "icon": "bi-heart-pulse-fill",
            "theme": "primary",
            "categories": [
                {"name": "Balanced Dietary Support Foods", "items": thyroid_foods}
            ],
            "pairing_tip": "Maintain a varied, balanced diet. Avoid taking high-dose iodine supplements unless specifically directed by your physician.",
            "clinical_note": "A thyroid condition should be evaluated using appropriate medical assessment and laboratory thyroid panels (TSH, Free T3, Free T4)."
        })

    # --- GENERAL BALANCED NUTRITION (DEFAULT IF NO SPECIFIC MODULE) ---
    if not guidance_blocks:
        general_categories = [
            {"name": "🥦 Vegetables & Fruits", "items": ["Leafy greens, berries, citrus fruits, bell peppers, carrots"]},
            {"name": "🍚 Whole Grains", "items": ["Quinoa, oats, brown rice, whole-wheat breads, barley"]},
            {"name": "🥚 Protein Sources", "items": ["Lentils, chickpeas, tofu, beans"] if is_vegetarian else ["Lentils, beans, tofu, eggs, fish, poultry"]},
            {"name": "🥛 Calcium & Vitamin D Rich Foods", "items": ["Fortified plant-based milks, sesame seeds, leafy greens"] if is_vegan else ["Dairy products, fortified plant beverages, eggs"]},
            {"name": "💧 Hydration", "items": ["Water as primary beverage throughout the day"]}
        ]

        guidance_blocks.append({
            "id": "general",
            "title": "General Balanced Nutrition Guidance",
            "icon": "bi-egg-fried",
            "theme": "primary",
            "categories": general_categories,
            "pairing_tip": "Aim for colorful, varied plates incorporating whole foods across all food groups.",
            "clinical_note": "Routine health checkups help monitor your wellness markers over time."
        })

    # 4. Flexible Example Meal Ideas (Adapted to Diet Preference)
    if is_vegan:
        breakfast = ["Oatmeal topped with berries, chia seeds, and fortified soy/almond milk", "Whole-grain toast with avocado and sliced tomatoes"]
        lunch = ["Warm quinoa bowl with roasted chickpeas, spinach, and tahini dressing", "Lentil vegetable soup with whole-grain bread"]
        snack = ["Apple slices with peanut butter", "Handful of mixed nuts and pumpkin seeds"]
        dinner = ["Tofu and vegetable stir-fry with brown rice", "Black bean and sweet potato bowl with leafy greens"]
    elif is_vegetarian:
        breakfast = ["Poached eggs on whole-grain toast with spinach", "Oatmeal with fruit, nuts, and fortified milk"]
        lunch = ["Chickpea and feta salad bowl with mixed greens", "Lentil soup with whole-grain crusty bread"]
        snack = ["Greek yogurt with berries", "Carrot and cucumber sticks with hummus"]
        dinner = ["Paneer/Tofu vegetable curry with brown rice", "Baked vegetable frittata with leafy green salad"]
    else:
        breakfast = ["Scrambled eggs with spinach and whole-grain toast", "Oatmeal topped with fruit and walnuts"]
        lunch = ["Grilled chicken/fish salad bowl with quinoa and vegetables", "Lentil bowl with fresh garden greens"]
        snack = ["Handful of almonds and fresh fruit", "Greek yogurt or cottage cheese"]
        dinner = ["Baked salmon/tofu with roasted vegetables and brown rice", "Lean poultry or bean chilli with mixed green salad"]

    meal_ideas = {
        "breakfast": breakfast,
        "lunch": lunch,
        "snack": snack,
        "dinner": dinner
    }

    # 5. Hydration & Lifestyle
    hydration_lifestyle = {
        "hydration": "Drink water regularly throughout the day according to your natural thirst and daily activity level. Limit sugar-sweetened beverages.",
        "lifestyle": [
            "Aim for 150 minutes of moderate physical activity weekly as appropriate for your fitness level.",
            "Prioritize 7-9 hours of restful sleep to support metabolic recovery.",
            "Maintain consistent meal timing to support steady digestive and metabolic health."
        ]
    }

    # 6. "Why am I seeing these suggestions?" Transparency sources
    why_sources = [
        f"Selected screening modules ({', '.join([m.title().replace('_', ' ') for m in selected_modules]) if selected_modules else 'General Health Baseline'})",
        f"Dietary preference ({diet_pref})",
        f"Known allergies ({known_allergies if has_allergies else 'None recorded'})",
        f"Checkup report evaluation ({latest_date})"
    ]

    return {
        "user_name": user.username if user else "User",
        "diet_pref": diet_pref,
        "has_allergies": has_allergies,
        "known_allergies": known_allergies,
        "selected_modules": selected_modules,
        "guidance_blocks": guidance_blocks,
        "meal_ideas": meal_ideas,
        "hydration_lifestyle": hydration_lifestyle,
        "why_sources": why_sources,
        "latest_date": latest_date,
        "disclaimer": "This is general nutrition guidance based on self-reported screening information, not a medical prescription or treatment plan. Consult a qualified healthcare professional or registered dietitian for personalized medical evaluation."
    }
