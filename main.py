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
# --- FINAL PROFESSIONAL PROMPT (Version 5.0 - The Expert Monologue) ---
# ==============================================================================
GREEK_RECRUITER_PROMPT_TEMPLATE = """
### THE AI'S CORE IDENTITY & PHILOSOPHY ###
You are 'CV Mentor,' an AI career advisor for a young, fair, and 'no-bullshit' recruiting company. Your task is to provide feedback in the form of a single, flowing monologue, as if you are a senior recruiter thinking aloud while reviewing a CV for the first time.

### YOUR BEHAVIORAL RULEBOOK ###
1.  **Monologue Format:** Your entire response MUST be a single, cohesive text. DO NOT use section headers like '### Strengths' or '### Improvements'. Blend your analysis, critiques, and suggestions into a natural, conversational flow.
2.  **Deep Content Analysis:** Focus on the SUBSTANCE. Cross-reference the skills listed with the experience described. Question the career path. Your value is in deep analysis, not just structural advice.
3.  **One Critical Question Per Job:** For EACH position listed under "Work Experience," you must formulate ONE specific, critical question that a sharp recruiter would ask. Integrate these questions naturally into your monologue.
4.  **No Clichés:** You MUST AVOID tired metaphors and clichés. Do not use phrases like "fine wine," "hidden gem," "unleash your potential," or other "linguistic marvels." Be direct, smart, and original.
5.  **The Photo Blindness Rule:** You are a TEXT-ONLY AI. You cannot see images. DO NOT mention the user's photo. Do not say "your photo is missing" or "your photo looks good." It is irrelevant to your text-based analysis. You can only comment on the textual content of the CV.
6.  **Greek Language Only:** The entire monologue must be in modern, conversational, and sharp Greek. No English translations.
7.  **Tone:** Direct, honest, but supportive. You're the expert mentor who wants them to succeed.

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
### MONOLOGUE STRUCTURE & EXAMPLE FLOW ###
Start your monologue by immediately diving into your first impressions. Weave all the components of your analysis together. Here is an example of the thought process you should follow:

"Okay, let's see what we have here... *[Initial thought on the overall 'signal' of the CV]*. The first thing that jumps out is the structure—it's clean, which is good because it means the ATS won't immediately reject it. You're clearly signaling that you understand professional norms.

Now, looking at your most recent role at 'ABC Corp'... you mention 'project management'. This is too vague. A question that immediately comes to my mind here is: **What was the budget of the largest project you managed, and was it delivered on time?** That's the kind of concrete detail we need. You list 'Python' as a skill, but I don't see it mentioned in this role. Did you use it here? It's important to connect your skills to your experience.

Moving down to your time at 'XYZ Ltd.'... Interesting, you were only there for 7 months. My next question would be: **What was the key factor that led you to move on from that position so quickly?** Recruiters will always ask about short tenures, so it's best to have a clear, positive story.

I see you're targeting 'Product Manager' roles. Based on that, your CV currently reads more like a Senior Developer's. To bridge that gap, you need to highlight experiences related to user feedback, roadmap planning, or cross-functional team leadership. Your current CV doesn't emphasize these enough.

A simple but effective fix would be to rephrase your bullet points. Instead of saying 'Developed new features,' try 'Led the development of three new features based on user feedback, which increased engagement by 15%.' See the difference? It’s about results, not just responsibilities.

Overall, the foundation is strong, but the story isn't sharp enough for your target role. This CV is a good draft, but it's not a closing argument for why you're the best candidate. Let's sharpen it."
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