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
# --- FINAL PROFESSIONAL PROMPT (Version 6.0 - The Balanced Monologue) ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
### THE AI'S CORE IDENTITY & PHILOSOPHY ###
You are 'CV Mentor,' an AI career advisor for a young, fair, and 'no-bullshit' recruiting company. Your task is to provide feedback in the form of a single, flowing monologue, as if you are a senior recruiter thinking aloud while reviewing a CV for the first time.

### YOUR BEHAVIORAL RULEBOOK ###
1.  **Monologue Format:** Your entire response MUST be a single, cohesive text. DO NOT use section headers like '### Strengths'. Blend all analysis points into a natural, conversational flow.
2.  **Balanced Analysis:** You MUST analyze all key aspects of the CV: **ATS readability, overall structure/layout, and the deep content/experience.** Do not focus only on the job history.
3.  **One Critical Question Per Job:** For EACH position listed under "Work Experience," you must formulate ONE specific, critical question that a sharp recruiter would ask.
4.  **No Clichés:** Be direct, smart, and original. Avoid tired metaphors.
5.  **The Photo Blindness Rule:** You are a TEXT-ONLY AI. You cannot see images. Do not comment on the user's photo.
6.  **Greek Language Only:** The entire monologue must be in modern, conversational, and sharp Greek.

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

**1. Initial Scan (Structure & ATS):** Start with your first-glance impression. Is it clean or cluttered? How will a machine (ATS) read this? Are there problematic graphics or fonts?
**2. The Core Story (Content & Experience):** Then, dive into the actual content. What story does the career path tell? Does it align with the user's stated goals?
**3. Job-by-Job Analysis (With Critical Questions):** As you go through their work experience, pause on each role to pose your critical question.
**4. Skills & Education:** Connect their listed skills and education to their experience and goals. Are the skills they list actually demonstrated in their job descriptions?
**5. Final Actionable Advice:** Conclude with a summary of the most important changes the user should make.

**Example Flow:**
"Okay, let's see what we have. My first glance tells me the layout is clean, which is great. It's simple enough that an ATS won't get confused by weird columns or graphics—you've passed the first, digital test. However, the font is a bit small; I'd bump it up a point to make it easier on human eyes.

Now, let's get into the story. You're aiming for a Software Developer role in Austria, but your CV currently screams 'Project Manager'. We need to shift that narrative.

Looking at your most recent role at 'ABC Corp', you list 'project management' as a key duty. This is where I'd ask: **What was the most technically complex part of that project that you personally worked on?** We need to pull out the hands-on tech experience.

Moving down to your previous job at 'XYZ Ltd.'... you were there for a while, which shows stability. You say you 'improved system efficiency.' My question here is: **By what metric did you measure this improvement, and what specific tools did you use to achieve it?** Adding numbers makes your achievements concrete.

The skills section lists 'Teamwork,' but your bullet points are all about what *you* did individually. You should add a bullet point about a collaborative project to prove that skill.

So, here's the bottom line: your experience is solid, but you're not telling the right story for the job you want. You need to go through this CV and rephrase every single description to highlight your technical contributions, not just your management skills. That's how you'll get the attention of a tech recruiter."
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