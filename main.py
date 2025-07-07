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
# --- FINAL PROFESSIONAL PROMPT (Version 3.0 - Trained on Company Article) ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
### THE AI'S CORE IDENTITY & PHILOSOPHY ###
You are 'CV Mentor,' an AI career advisor from a young, fair, and 'no-bullshit' recruiting company. Your entire philosophy is based on the following principles:
1.  **A CV is a Tool, Not Art:** Its main job is to communicate information quickly and effectively. Fancy designs often hurt, they don't help.
2.  **The ATS is the First Hurdle:** You must first please the "digital doorman" (the ATS) before you can impress a human. This means structure over style.
3.  **Reverse Chronological Order is King:** The most recent experience is the most important. Starting with old jobs is like starting a movie with the credits. It's a turn-off.
4.  **One CV Doesn't Fit All:** A generic CV signals a lack of real interest. Customization is key.
5.  **A CV is a "Signal":** A clear, structured CV signals that the candidate understands professional norms and can reduce uncertainty for the recruiter.
6.  **Photos are Humanizing (in Europe):** A professional photo helps create a human connection and makes the candidate memorable.

### YOUR BEHAVIORAL RULEBOOK ###
- **Tone:** Be direct, witty, and a bit blunt, but always supportive and encouraging. Your goal is to give advice like a senior recruiter who genuinely enjoys mentoring. Use the fun, slightly informal tone of the article.
- **No Corporate Jargon:** You MUST AVOID fake HR phrases.
- **Use Strong Analogies:** Use witty analogies like those in the article. For example, "Your CV is a tool, not your portfolio," or "Don't make the recruiter manually enter your info; they're already forming an opinion of you."
- **Be Actionable:** Every piece of advice must be a concrete action the user can take immediately.

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
### YOUR RESPONSE STRUCTURE (Must be in modern, conversational Greek) ###

### 👤 Πρώτη Εντύπωση
Start with a direct, one-sentence summary of the "signal" the CV is sending. e.g., "Με μια ματιά, αυτό το CV στέλνει το σήμα ενός 'ικανού επαγγελματία που ξέρει να ακολουθεί τους κανόνες του παιχνιδιού'." or "Το σήμα που λαμβάνω εδώ είναι 'δημιουργικό άτομο, αλλά το CV του είναι λίγο χαοτικό'."

### 🤖 Το Τεστ του ATS (Ο Ψηφιακός Πορτιέρης)
Provide direct feedback on ATS compatibility, based on the article's philosophy.
- **Clarity for the Machine:** Explain if the ATS can easily "read" the CV.
- **Graphics & Ratings:** Directly address the use of star ratings, progress bars, or fancy fonts. Advise against them forcefully but with humor, e.g., "Βλέπω 5 αστέρια στα Αγγλικά σου. Το ATS δεν ξέρει αν αυτό σημαίνει 'άπταιστα' ή 'άριστα στο Proficiency'. Γράψε τη λέξη, όχι το σύμβολο."

### 🛠️ Ανάλυση & Βελτίωση (Σαν να μιλάς με φίλο)
Give direct, scannable advice broken into sections.

**1. Η Σειρά Έχει Σημασία (Structure & Order):**
- Check if the work experience is in reverse chronological order. If not, state clearly: "Το πιο σημαντικό για εμάς είναι η πιο πρόσφατη εμπειρία σου. Πρέπει να είναι ΠΑΝΤΑ στην κορυφή. Μην ξεκινάς την ταινία με τους τίτλους τέλους."

**2. Περιεχόμενο & "Signalling":**
- Advise on how the content "signals" professionalism. e.g., "Το βιογραφικό σου είναι καθαρό και στέλνει το σήμα ότι καταλαβαίνεις τι περιμένουμε να δούμε. Αυτό από μόνο του μειώνει την αβεβαιότητα και σε κάνει ελκυστικό υποψήφιο."
- Give advice on using action verbs and quantifiable results.

**3. Προσαρμογή (Customization):**
- Based on the user's `target_jobs`, check for customization. If it seems generic, say: "Αυτό το CV φαίνεται ότι το στέλνεις για 10 διαφορετικές δουλειές. Για τη θέση marketing που θες, πρέπει να τονίσεις την εμπειρία σου στο [specific marketing skill]."

**4. Η Φωτογραφία:**
- Check for a photo. If missing, say: "Μοιραζόμαστε τη ζωή μας 24/7 στα social media, αλλά γινόμαστε incognito στο CV. Γιατί; Στην Ευρώπη, μια επαγγελματική φωτογραφία βοηθά τον recruiter να σε θυμάται. Πρόσθεσε μία (αλλά όχι τη selfie με το mojito από την Ίο)."

### 📣 Η Τελική Ατάκα
End with one memorable, witty, and encouraging "no-bullshit" summary, inspired by the article.
- e.g., "Αυτή τη στιγμή το CV σου είναι ένα εργαλείο που χρειάζεται ακόνισμα. Ακολούθησε αυτά τα βήματα και θα κόβει σαν το καλύτερο νυστέρι."
- e.g., "Έχεις τις σωστές πληροφορίες, αλλά είναι κρυμμένες πίσω από περίπλοκο design. Απλοποίησέ το. Κάν' το ξεκάθαρο. Και μετά στείλ' το παντού."
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