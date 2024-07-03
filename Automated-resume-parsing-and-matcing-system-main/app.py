import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from fpdf import FPDF
import json
from io import BytesIO
import time

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_gemini_response(input, retries=3):
    model = genai.GenerativeModel('gemini-pro')
    for attempt in range(retries):
        try:
            response = model.generate_content(input)
            if response and response.text:
                return response.text
        except Exception as e:
            st.error(f"Attempt {attempt + 1} failed: {e}")
        time.sleep(2)  
    return None

def input_pdf_text(uploaded_file):
    text = ""
    with BytesIO(uploaded_file.getvalue()) as file:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()
    return text

input_prompt = """
Hey, act like a skilled or very experienced ATS (Application Tracking System)
with a deep understanding of the tech field, including software engineering, data science, data analysis, Java development, frontend engineering, backend engineering, full-stack engineering, and big data engineering. Your task is to evaluate the resume based on the given job description. You must consider the job market is very competitive and you should provide the best assistance for improving the resumes. Assign the percentage matching based on JD and the missing keywords with high accuracy.
Extract the information in the following structure:
{{
    "JD Match": "%",
    "Missing Keywords": [],
    "Years of experience": "years",
    "Profile Summary": "",
    "Personal Information": {{
        "Name": "",
        "Phone": "",
        "Email": ""
    }},
    "Skills": [],
    "Work Experience": [],
    "Education": []
}}
resume:{text}
description:{jd}
"""

def create_resume(details):
    skills = f"Proficient in {', '.join(details.get('Skills', ['Not specified']))}."

    work_experience_list = details.get("Work Experience", [])
    work_experience = "\n".join(
        [f"{i+1}) Company: {we.get('Company', 'Not specified')}\n   Position: {we.get('Position', 'Not specified')}\n   Duration: {we.get('Duration', 'Not specified')}\n  Description: {we.get('Description', 'Not specified')}" 
         for i, we in enumerate(work_experience_list)]
    ) or "Not specified"

    education_list = details.get("Education", [])
    education = "\n".join(
        [f"{i+1}) School: {edu.get('Institution', 'Not specified')}\n   Degree: {edu.get('Degree', 'Not specified')}\n   Duration: {edu.get('Duration', 'Not specified')}" 
         for i, edu in enumerate(education_list)]
    ) or "Not specified"
    
    resume_text = f"""
Personal Information:
    Name: {details["Personal Information"].get('Name', 'Not specified')}
    Phone: {details["Personal Information"].get('Phone', 'Not specified')}
    Email: {details["Personal Information"].get('Email', 'Not specified')}

Professional Summary:
    {details.get("Profile Summary", "Not specified")}

Skills:
    {skills}

Work Experience:
    {work_experience}

Education:
    {education}
"""
    return resume_text

def set_pdf_style(pdf):
    pdf.set_fill_color(46, 46, 56)  # Background color
    pdf.rect(0, 0, 210, 297, 'F')  # Apply background color to entire page
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(255, 255, 255)  # Text color

def save_pdf(resume_text, filename):
    pdf = FPDF()
    pdf.add_page()
    set_pdf_style(pdf)  # Apply styles to the first page
    
    resume_lines = resume_text.strip().split('\n')
    line_height = pdf.font_size * 1.5

    x_start = pdf.l_margin
    y_start = pdf.t_margin

    personal_details = []
    other_lines = []
    is_personal_section = False
    for line in resume_lines:
        if "Personal Information:" in line:
            is_personal_section = True
        elif is_personal_section and line.strip() == "":
            is_personal_section = False
        if is_personal_section:
            personal_details.append(line)
        else:
            other_lines.append(line)

    personal_text = "\n".join(personal_details)
    personal_height = len(personal_details) * line_height
    personal_y = pdf.t_margin
    pdf.set_xy(x_start, personal_y)
    pdf.multi_cell(pdf.w - 2 * pdf.l_margin, line_height, txt=personal_text.encode('latin-1', 'replace').decode('latin-1'), border=0, align="L", fill=False)
    
    logo_x = pdf.w - pdf.r_margin - 30  
    logo_y = personal_y
    pdf.image("ey_logo.png", x=logo_x, y=logo_y, w=30)  

    current_y = personal_y + personal_height + 10

    section_titles = ["Skills:", "Professional Summary:", "Work Experience:", "Education:"]

    for line in other_lines:
        if any(line.startswith(title) for title in section_titles):
            pdf.set_xy(x_start, current_y)
            pdf.multi_cell(pdf.w - 2 * pdf.l_margin, line_height, txt=line.encode('latin-1', 'replace').decode('latin-1'), border=0, align="L", fill=False)
            current_y = pdf.get_y() + 1  
            pdf.set_draw_color(255, 255, 0)  
            pdf.set_line_width(0.5)  
            pdf.line(x_start, current_y, pdf.w - pdf.r_margin, current_y)  
            current_y += 2  
        else:
            if current_y + line_height > pdf.h - pdf.b_margin:
                pdf.add_page()
                set_pdf_style(pdf)
                current_y = pdf.t_margin
            
            pdf.set_xy(x_start, current_y)
            pdf.multi_cell(pdf.w - 2 * pdf.l_margin, line_height, txt=line.encode('latin-1', 'replace').decode('latin-1'), border=0, align="L", fill=False)
            current_y = pdf.get_y()

    pdf.output(filename, 'F')

st.title("EY ATS")
st.text("Improve Your Resume ATS")
jd = st.text_area("Paste the Job Description")
uploaded_file = st.file_uploader("Upload Your Resume", type="pdf", help="Please upload the pdf")

submit = st.button("Submit")

if submit and uploaded_file:
    text = input_pdf_text(uploaded_file)
    prompt = input_prompt.format(text=text, jd=jd)
    response = get_gemini_response(prompt)

    st.text("Raw Response:")
    st.text(response)

    if not response:
        st.error("The AI response was empty. Please try again.")
    else:
        try:
            details = json.loads(response)
        except json.JSONDecodeError as e:
            st.error(f"Failed to decode response: {e}")
            st.text_area("Response Content", response)  
        else:
            resume_text = create_resume(details)

            pdf_filename = f"{details['Personal Information'].get('Name', 'Not_specified')}_generated_resume.pdf"
            save_pdf(resume_text, pdf_filename)

            st.subheader("AI Evaluation and Generated Resume")
            st.text_area("Profile Summary", details.get("Profile Summary", "Not specified"))
            st.text(f"JD Match: {details.get('JD Match', 'Not specified')}")
            st.text(f"Missing Keywords: {', '.join(details.get('Missing Keywords', ['Not specified']))}")

            with open(pdf_filename, "rb") as f:
                st.download_button("Download Generated Resume", f, file_name=pdf_filename)
