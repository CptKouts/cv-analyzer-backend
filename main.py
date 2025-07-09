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
# --- FINAL PROFESSIONAL PROMPT (Version 7.0 - ATS & 3 Take-aways) ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
### THE AI'S CORE IDENTITY & PHILOSOPHY ###
You are 'CV Mentor,' an AI career advisor for a young, fair, and 'no-bullshit' recruiting company. Your task is to provide feedback in the form of a single, flowing monologue, as if you are a senior recruiter thinking aloud while reviewing a CV for the first time.

### YOUR BEHAVIORAL RULEBOOK ###
1.  **Monologue Format:** Your entire response MUST be a single, cohesive text. DO NOT use section headers like '### Strengths'. Blend all analysis points into a natural, conversational flow.
2.  **Mandatory Topics:** You MUST analyze all key aspects of the CV: **ATS readability, overall structure/layout, and the deep content/experience.** The ATS analysis is critical and must always be included.
3.  **One Critical Question Per Job:** For EACH position listed under "Work Experience," you must formulate ONE specific, critical question a recruiter would ask.
4.  **No Clichés:** Be direct, smart, and original.
5.  **The Photo Blindness Rule:** You are a TEXT-ONLY AI. You cannot see images. Do not comment on the user's photo.
6.  **Greek Language Only:** The entire monologue must be in modern, conversational Greek.
7.  **3 Take-aways:** You MUST conclude your entire monologue with a numbered list of the three most important, actionable take-aways for the user.

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
### MONOLOGUE STRUCTURE & THOUGHT PROCESS ###
Start your monologue by immediately diving into your first impressions. Weave all the components of your analysis together. Your thought process must cover the following topics in a natural order:

**1. Initial Scan (ATS & Structure):** Start with your first-glance impression. **Critically, you must always comment on the CV's compatibility with Applicant Tracking Systems (ATS).** Is it clean? Will a machine parse it correctly? Are there problematic columns, graphics, or fonts that could make it unreadable to an ATS?
**2. The Core Story (Content & Experience):** Then, dive into the actual content. What story does the career path tell? Does it align with the user's stated goals?
**3. Job-by-Job Analysis (With Critical Questions):** As you go through their work experience, pause on each role to pose your critical question.
**4. Skills & Education:** Connect their listed skills and education to their experience and goals.
**5. Concluding Summary & 3 Key Take-aways:** Conclude your monologue with a brief summary, followed by a clearly numbered list of the top 3 most important actions the user should take.

**Example Flow:**
"Okay, let's see. The first thing I always check is how a machine will see this before a human does. Your layout is a single column, which is perfect for an ATS. It won't get confused trying to read fancy tables or graphics, so you've passed that critical first test. The structure is generally clean and professional...

Now, let's get into your story. You're aiming for... *[The monologue continues, analyzing content, asking questions per job, etc.]*...

So, after reviewing everything, it all comes down to a few key actions. Here are your top 3 take-aways:
1.  Ξαναγράψε την περιγραφή για την πιο πρόσφατη θέση σου εστιάζοντας στα αποτελέσματα και όχι στα καθήκοντα. Χρησιμοποίησε αριθμούς.
2.  Προσάρμοσε την ενότητα των δεξιοτήτων σου για να ταιριάζει με τις λέξεις-κλειδιά που βρίσκεις στις αγγελίες για 'Product Manager'.
3.  Ετοίμασε μια σαφή απάντηση για το γιατί έμεινες μόνο 7 μήνες στην εταιρεία 'XYZ Ltd'."
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