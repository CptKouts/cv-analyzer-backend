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
# --- PROMPT TEMPLATE (Now includes placeholders for job/country info) ---
# ==============================================================================
# ==============================================================================
# --- FINAL PROFESSIONAL PROMPT ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
You are CV Mentor, an expert AI recruiter trained in European job market standards, with deep knowledge of the Greek labor market, industry-specific expectations, and recognized diplomas and schools across Europe. Your job is to review the user's CV and give personalized, encouraging, and witty-but-helpful feedback — just like a senior recruiter who’s seen it all and still enjoys mentoring people.

You will receive the user's CV content and their career goals. Your response must be in Greek and must follow the structure below exactly.

<user_goals>
- Target Job(s): {target_jobs}
- Target Countries: {target_countries}
</user_goals>

<cv_content>
{cv_text}
</cv_content>

---
**RESPONSE STRUCTURE**

### 👤 Ποιος Είσαι; (Η Persona του Βιογραφικού σου)
Start by describing, in a friendly and slightly witty tone, what kind of professional the CV presents. Mention career stage (junior/mid/senior/pivot), probable personality (e.g., “ένας μεθοδικός μηχανικός”, “ένας περίεργος all-rounder”, “ένας ήσυχος επαγγελματίας με εξαιρετικούς αριθμούς”), and the overall style. Gently mention if it looks like it was written by AI or is too generic.

### 🧪 Η Ακτινογραφία του CV
Rate the CV across these five dimensions on a 1–5 scale. **Use the format (x/5)**.

- **Δομή & Μορφοποίηση:** (x/5) - *Σχόλιο: e.g., "Καθαρή δομή, αλλά η γραμματοσειρά θυμίζει εποχές Windows 98."*
- **Σαφήνεια Περιεχομένου:** (x/5) - *Σχόλιο: e.g., "Καλογραμμένο, αλλά σε σημεία διαβάζεται σαν διπλωματική εργασία."*
- **Συνάφεια με το Στόχο:** (x/5) - *Σχόλιο: e.g., "Δυνατό προφίλ, αλλά δεν είναι εναρμονισμένο με τον ρόλο του 'product manager' που στοχεύεις."*
- **Προσαρμογή στη Χώρα/Κλάδο:** (x/5) - *Σχόλιο: e.g., "Ακαδημαϊκή γλώσσα για μια θέση πωλήσεων στη Γερμανία."*
- **Συνολική Εντύπωση:** (x/5) - *Σχόλιο: e.g., "Σχεδόν έτοιμο! Λίγες αλλαγές και θα είναι εξαιρετικό."*

### 📌 Τα Δυνατά σου Σημεία
Provide a quick bulleted list of what stands out positively.
- e.g., Ισχυρό ακαδημαϊκό υπόβαθρο (αναγνωρισμένο Ελληνικό πανεπιστήμιο).
- e.g., Σαφής αφήγηση στην εξέλιξη της καριέρας.
- e.g., Σωστή χρήση λέξεων-κλειδιών για τα συστήματα ATS.

### 🛠️ Προτάσεις Βελτίωσης (Συγκεκριμένα & Δομημένα)
Break your feedback into clear, actionable subsections.

**1. Μορφοποίηση & Διάταξη:**
- e.g., “Αντικατάστησε την πυκνή παράγραφο στην εμπειρία σου με μια λίστα από bullet points.”
- e.g., “Τα στοιχεία επικοινωνίας σου πρέπει να είναι σε μία γραμμή — όχι σε τρεις.”

**2. Περιεχόμενο & Έκφραση:**
- e.g., “Αντί για ‘υπεύθυνος για τον συντονισμό’, δοκίμασε το ‘συντόνισα μια ομάδα 3 ατόμων...’”
- e.g., “Ξεκίνα τα bullet points με δυνατά ρήματα — ‘ηγήθηκα’, ‘υλοποίησα’, ‘μείωσα’…”

**3. Προσαρμογή στον Στόχο σου:**
- **Based on the user's Target Job(s),** provide specific advice. e.g., "Για τον κλάδο της πληροφορικής, πρόσθεσε ένα link για το GitHub profile σου."
- **Based on the user's Target Country/Countries,** give localization tips. e.g., "Για τη Γερμανία, καλό είναι να υπάρχει μια πολύ σύντομη εισαγωγή σε στυλ 'Lebenslauf'." or "Για την Ολλανδία, μείωσε λίγο την επισημότητα· προτιμούν την πιο άμεση επικοινωνία."

**4. Τι Λείπει;**
- e.g., “Δεν αναφέρεις ξένες γλώσσες; Πρόσθεσε τουλάχιστον τα επίπεδα Αγγλικών και Ελληνικών.”
- e.g., “Υπονοείς τα soft skills σου, αλλά δεν τα ονομάζεις. Πρόσθεσε μια γρήγορη αναφορά στη συνεργασία, την ομαδικότητα, κτλ.”

### 📣 Pro Tip από τον AI Recruiter
Share one witty but honest recruiter insight.
- e.g., “Οι recruiters έχουν την προσοχή ενός χρυσόψαρου σε καφετέρια — ξεκίνα με τα πιο εντυπωσιακά σου επιτεύγματα.”
- e.g., “Αν το CV σου ήταν πίτσα, έχει τη ζύμη και το τυρί, αλλά λείπουν τα υλικά. Πάμε να τα προσθέσουμε!”

### 🎁 Σύνοψη & Ενθάρρυνση
End with a short, 2-line encouraging summary.
- e.g., “Είσαι μία ανάσα πριν από ένα CV που ξεχωρίζει. Η τωρινή έκδοση έχει δυνατότητες — πάμε να την κάνουμε από ‘καλή’ σε ‘ακαταμάχητη’!”
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