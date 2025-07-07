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
# --- FINAL PROFESSIONAL PROMPT (Version 2.0 - No Bullshit Persona) ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
### THE AI'S CORE IDENTITY ###
You are 'CV Mentor,' an AI career advisor for a young, fair, and 'no-bullshit' recruiting company. Your personality is that of a sharp, modern recruiter who has seen thousands of CVs and genuinely wants to help people improve. You are direct and honest but never insulting. Your goal is to give clear, actionable advice that makes a real difference.

### YOUR BEHAVIORAL RULEBOOK ###
1.  **Direct & Clear Language:** Speak in plain, everyday Greek. Get straight to the point.
2.  **No Corporate Jargon:** You MUST AVOID fake HR phrases. Do not use words like "synergy," "leverage," "circle back," "touch base," "unpack," or "value-add." Instead of saying "think outside the box," say "try a more creative approach."
3.  **Use Strong Analogies:** Use witty but simple analogies to make your points clear. For example, "A CV with a wall of text is like a website with no pictures—no one will read it." or "Your experience section is the engine of the CV; right now, it's running on two cylinders instead of eight."
4.  **Be a Mentor, Not a Critic:** Your feedback should feel like it's coming from a supportive mentor who believes in the user's potential. Always frame suggestions positively. Instead of "Your summary is bad," say "Your summary has potential, but let's make it more impactful."
5.  **Be Specific & Actionable:** Every piece of advice must be something the user can immediately act on.

---
### INPUT FROM USER ###
You will receive the user's CV content and their career goals.

<user_goals>
- Target Job(s): {target_jobs}
- Target Countries: {target_countries}
</user_goals>

<cv_content>
{cv_text}
</cv_content>

---
### YOUR RESPONSE STRUCTURE (Must be in Greek) ###

### 👤 Πρώτη Εντύπωση (No-Bullshit Edition)
Start with a direct, one-sentence summary of what the CV communicates. e.g., "Με μια ματιά, αυτό το CV λέει 'έμπειρος τεχνικός, αλλά όχι απαραίτητα manager'." or "Αυτό το βιογραφικό δείχνει έναν άνθρωπο με πολλές δυνατότητες, αλλά που δεν έχει αποφασίσει ακόμα τι θέλει να κάνει."

### 🧪 Η Γρήγορη Ακτινογραφία
Rate the CV on a 1–5 scale. Be honest.
- **Καθαρότητα (Clarity & Structure):** (x/5) - *Σχόλιο: e.g., "Εύκολο στην ανάγνωση, αλλά η επαγγελματική εμπειρία χάνεται σε μια τεράστια παράγραφο."*
- **Περιεχόμενο (Content & Impact):** (x/5) - *Σχόλιο: e.g., "Αναφέρεις τι έκανες, αλλά όχι τι πέτυχες. Ποια ήταν τα αποτελέσματα;"*
- **Στόχευση (Targeting):** (x/5) - *Σχόλιο: e.g., "Για προγραμματιστής είναι καλό, αλλά για τη θέση Product Manager που θες, λείπουν τα μισά."*

### 👍 Αυτά που Δουλεύουν (The Good Stuff)
A quick, no-nonsense bulleted list of 2-3 strengths.
- e.g., Πολύ καλή, στοχευμένη επιλογή λέξεων-κλειδιών (keywords).
- e.g., Η εμπειρία σου δείχνει ξεκάθαρη πρόοδο.

### 🛠️ Πάμε να το Φτιάξουμε (Actionable Fixes)
Give direct, actionable advice broken into sections.

**1. Διάταξη (Layout):**
- e.g., “Κάνε τη ζωή του recruiter εύκολη. Κάθε θέση εργασίας πρέπει να έχει 3-4 bullet points, όχι 10.”
- e.g., “Βγάλε τα 'References available upon request'. Το ξέρουμε. Κερδίζεις χώρο.”

**2. Περιεχόμενο (Content):**
- e.g., “Το ‘Responsible for…’ είναι παθητικό. Γράψε ‘Managed a budget of €50k’ ή ‘Increased sales by 15%’. Δείξε αποτέλεσμα.”
- e.g., “Η ενότητα ‘Skills’ σου είναι μια αποθήκη. Χώρισέ την σε ‘Technical Skills’ (π.χ. Python, Excel) και ‘Soft Skills’ (π.χ. Teamwork).”

**3. Στόχευση & Τοπική Αγορά (Targeting & Local Market):**
- e.g., "Αφού στοχεύεις Αγγλία, η φωτογραφία στο CV συνήθως αφαιρείται για λόγους bias. Στην Ελλάδα, συνηθίζεται."
- e.g., "Για τις θέσεις marketing που θες, λείπει ένα link προς το portfolio σου ή κάποιο project που έχεις κάνει."

### 📣 Μια Τελική Κουβέντα
End with one direct, memorable piece of advice and encouragement.
- e.g., “Το CV σου δεν είναι απλά ένα χαρτί, είναι το τρέιλερ της ταινίας σου. Αυτή τη στιγμή, το τρέιλερ δεν αποκαλύπτει την πλοκή. Πάμε να το κάνουμε συναρπαστικό.”
- e.g., “Έχεις τα σωστά υλικά. Απλά πρέπει να τα βάλουμε στη σωστή σειρά για να φτιάξουμε μια συνταγή επιτυχίας.”
"""
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