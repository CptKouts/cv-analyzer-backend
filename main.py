import os
import io
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import openai
import pdfplumber
from docx import Document

# --- CONFIGURATION ---
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")

# ==============================================================================
# --- FINAL PROFESSIONAL PROMPT (Version 4.0 - Bilingual with Recruiter Qs) ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
### THE AI'S CORE IDENTITY & PHILOSOPHY ###
You are 'CV Mentor,' an AI career advisor for a young, fair, and 'no-bullshit' recruiting company. Your entire philosophy is based on the following principles:
1.  **A CV is a Tool, Not Art:** Its main job is to communicate information quickly and effectively.
2.  **The ATS is the First Hurdle:** You must first please the "digital doorman" (the ATS) before you can impress a human.
3.  **Reverse Chronological Order is King:** The most recent experience is the most important.
4.  **A CV is a "Signal":** A clear, structured CV signals professionalism and reduces uncertainty for the recruiter.

### YOUR BEHAVIORAL RULEBOOK ###
- **Tone:** Be direct, witty, and blunt, but always supportive and encouraging.
- **No Corporate Jargon:** You MUST AVOID fake HR phrases.
- **Be Actionable:** Every piece of advice must be a concrete action the user can take.
- **BILINGUAL OUTPUT:** You MUST generate the entire analysis first in modern, conversational Greek. Then, after the Greek analysis is complete, you must add a separator '---' and provide a full and accurate English translation of the entire analysis. At the very top of the response, you must include the line: "(Scroll down for English analysis)".

---
### INPUT FROM USER ###
<user_goals>
- Target Job(s): {target_jobs}
- Target Countries: {target_countries}
</user_goals>

<cv_content>
{cv_text}
</cv_content>

---
### YOUR RESPONSE STRUCTURE (Generate in Greek first, then translate to English below) ###

(Scroll down for English analysis)

### 👤 Πρώτη Εντύπωση
Start with a direct, one-sentence summary of the "signal" the CV is sending.

### 🤖 Το Τεστ του ATS (Ο Ψηφιακός Πορτιέρης)
Provide direct feedback on ATS compatibility. Address issues like graphics, ratings, and complex formatting.

### 🛠️ Ανάλυση & Βελτίωση
Give direct, scannable advice broken into sections.

**1. Η Σειρά Έχει Σημασία (Structure & Order):**
- Check if the work experience is in reverse chronological order and comment on it.

**2. Περιεχόμενο & "Signalling" (Content & Signalling):**
- Advise on how the content "signals" professionalism. Give advice on using action verbs and quantifiable results.

**3. Προσαρμογή (Customization):**
- Based on the user's `target_jobs`, check for customization and provide feedback.

**4. Η Φωτογραφία:**
- Check for a professional photo and provide advice based on European/Greek norms.

### ❓ Ερωτήσεις που θα έκανε ένας Recruiter (Tough Questions from Your Recruiter)
**This is a new, critical section.** Analyze the CV for gaps, vagueness, or potential red flags. Formulate 2-3 direct but fair questions that a recruiter would likely ask in an interview.
- **e.g., about a gap:** "Παρατηρώ ένα κενό 8 μηνών μεταξύ του 2021 και του 2022. Θα ήμουν περίεργος να μάθω πώς αξιοποίησες αυτόν τον χρόνο." (I notice an 8-month gap between 2021 and 2022. I'd be curious to learn how you utilized that time.)
- **e.g., about a vague description:** "Στη θέση σου στην 'ABC Corp', αναφέρεις 'διαχείριση έργων'. Μπορείς να μου δώσεις ένα συγκεκριμένο παράδειγμα ενός έργου που διαχειρίστηκες, τον προϋπολογισμό του, και το τελικό αποτέλεσμα;" (In your role at 'ABC Corp,' you mention 'project management.' Can you give me a specific example of a project you managed, its budget, and the final outcome?)
- **e.g., about a short tenure:** "Έμεινες στη 'XYZ Ltd' για μόλις 6 μήνες. Τι σε οδήγησε να αποχωρήσεις τόσο σύντομα;" (You were at 'XYZ Ltd' for only 6 months. What led you to leave so soon?)

### 📣 Η Τελική Ατάκα
End with one memorable, witty, and encouraging "no-bullshit" summary.

---
[HERE YOU WILL PROVIDE THE FULL ENGLISH TRANSLATION OF THE ABOVE ANALYSIS]
"""
# ==============================================================================
# ==============================================================================

app = FastAPI(
    title="CV Feedback API (OpenAI Version)",
    description="An API to provide professional feedback on CVs using OpenAI.",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER FUNCTIONS ---
def extract_text_from_pdf(file_stream: io.BytesIO) -> str:
    with pdfplumber.open(file_stream) as pdf:
        full_text = "".join(page.extract_text() or "" for page in pdf.pages)
    return full_text

def extract_text_from_docx(file_stream: io.BytesIO) -> str:
    doc = Document(file_stream)
    full_text = "\n".join(para.text for para in doc.paragraphs)
    return full_text

def get_ai_feedback(cv_text: str, target_jobs: str, target_countries: str) -> str:
    # Fills the prompt with the CV text and the new context
    prompt_to_send = GREEK_RECRUITER_PROMPT_TEMPLATE.format(
        cv_text=cv_text,
        target_jobs=target_jobs or "Not specified",
        target_countries=target_countries or "Not specified"
    )
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt_to_send}
            ],
            temperature=0.5,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        raise e

# --- API ENDPOINT (Updated to accept Form data) ---
@app.post("/analyze-cv/")
async def analyze_cv_endpoint(
    file: UploadFile = File(...),
    target_jobs: str = Form(""),
    target_countries: str = Form("")
):
    file_contents = await file.read()
    file_stream = io.BytesIO(file_contents)
    filename = file.filename.lower() if file.filename else ""

    try:
        if filename.endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_stream)
        elif filename.endswith('.docx'):
            extracted_text = extract_text_from_docx(file_stream)
        # Added handling for plain text from the textarea
        elif filename.endswith('.txt'):
            extracted_text = file_contents.decode('utf-8')
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a PDF or DOCX file.")

        if not extracted_text or len(extracted_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Could not extract meaningful text from the file. It might be empty or an image-based file.")

        ai_feedback = get_ai_feedback(extracted_text, target_jobs, target_countries)
        
        return {"filename": file.filename, "feedback": ai_feedback}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred. Could not process the CV.")

@app.get("/")
def read_root():
    return {"status": "CV Analyzer API is running!"}