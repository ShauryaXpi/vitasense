import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_screening_pdf(output_path, user_name, user_email, report_data, profile_data=None):
    """
    Generates a personalized PDF report containing only the selected screening modules,
    visual summaries, questionnaire summaries, lab findings, recommendations, and disclaimers.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0a2540')
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#6c757d')
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0d6efd'),
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#212529')
    )

    disclaimer_style = ParagraphStyle(
        'DisclaimerText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#495057')
    )

    elements = []

    # Header
    elements.append(Paragraph("VitaSense Health Screening Report", title_style))
    elements.append(Paragraph(f"Preliminary Multimodal Screening Report &bull; Date: {report_data.get('created_at', 'Sep 15, 2026')}", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0d6efd'), spaceAfter=12))

    # Patient & Intake Info Table
    patient_info = [
        [Paragraph("<b>Patient Name:</b>", body_style), Paragraph(user_name or "Valued Patient", body_style),
         Paragraph("<b>Email:</b>", body_style), Paragraph(user_email or "N/A", body_style)],
    ]
    if profile_data:
        patient_info.append([
            Paragraph(f"<b>Age:</b> {profile_data.get('age', 'N/A')} yrs", body_style),
            Paragraph(f"<b>Sex:</b> {profile_data.get('sex', 'N/A')}", body_style),
            Paragraph(f"<b>Height:</b> {profile_data.get('height', 'N/A')} {profile_data.get('height_unit', '')}", body_style),
            Paragraph(f"<b>Weight:</b> {profile_data.get('weight', 'N/A')} {profile_data.get('weight_unit', '')}", body_style)
        ])

    info_table = Table(patient_info, colWidths=[100, 160, 100, 180])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # Selected Screening Modules Results
    elements.append(Paragraph("Selected Screening Module Results", h2_style))
    
    results_list = report_data.get('results', [])
    if results_list:
        table_data = [
            [Paragraph("<b>Screening Area</b>", body_style),
             Paragraph("<b>Estimated Risk Level</b>", body_style),
             Paragraph("<b>Score</b>", body_style)]
        ]
        for res in results_list:
            cat = res.get('category', 'Lower screening risk')
            score_str = f"{res.get('score', 0)}%"
            table_data.append([
                Paragraph(res.get('title', 'Screening Area'), body_style),
                Paragraph(f"<b>{cat}</b>", body_style),
                Paragraph(score_str, body_style)
            ])

        res_table = Table(table_data, colWidths=[240, 200, 100])
        res_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e7f1ff')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(res_table)
    else:
        elements.append(Paragraph("General Preliminary Health Risk Evaluation Completed.", body_style))

    elements.append(Spacer(1, 12))

    # Observations & Questionnaire Factors
    elements.append(Paragraph("Visual & Intake Factors Evaluated", h2_style))
    vis_summary = report_data.get('visual_summary') or "Observational image features processed for eyes, tongue, and nails."
    q_summary = report_data.get('questionnaire_summary') or "Guided symptom and diet intake responses recorded."
    
    elements.append(Paragraph(f"<b>Visual Features:</b> {vis_summary}", body_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"<b>Questionnaire Intake:</b> {q_summary}", body_style))
    elements.append(Spacer(1, 10))

    # Lab Findings (if available)
    if report_data.get('has_lab_report') or report_data.get('lab_findings'):
        elements.append(Paragraph("Laboratory Findings", h2_style))
        lab_findings = report_data.get('lab_findings') or "Laboratory biomarkers extracted and cross-referenced with screening benchmarks."
        elements.append(Paragraph(lab_findings, body_style))
        elements.append(Spacer(1, 10))

    # Recommended Next Steps
    elements.append(Paragraph("Recommended Next Steps", h2_style))
    rec_text = "Review these preliminary screening indicators with a qualified healthcare professional. Consider standard clinical blood testing if recommended by your physician."
    elements.append(Paragraph(rec_text, body_style))
    elements.append(Spacer(1, 15))

    # Medical Disclaimer Notice
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#ced4da'), spaceAfter=8))
    disclaimer = (
        "<b>Medical Disclaimer:</b> This report provides preliminary health-screening information and is not a medical diagnosis. "
        "Please consult a qualified healthcare professional for medical evaluation and diagnosis."
    )
    elements.append(Paragraph(disclaimer, disclaimer_style))

    doc.build(elements)
    return output_path
