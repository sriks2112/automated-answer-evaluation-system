import os
from datetime import datetime
from urllib.parse import quote_plus

from mistralai import Mistral
from sentence_transformers import SentenceTransformer, util
from pymongo import MongoClient


# =========================
# CONFIG
# =========================
API_KEY = "your_key"

MODEL_ANSWER_PDF = "model ans.pdf"
STUDENT_ANSWER_PDF = "kanihw.pdf"

OCR_MODEL = "mistral-ocr-latest"

MONGO_USERNAME = "your_username"
MONGO_PASSWORD = quote_plus("your_password")
MONGO_URI = (
    f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}"
    "@cluster0.h2whavl.mongodb.net/aae?retryWrites=true&w=majority"
)


# =========================
# DATABASE
# =========================
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["aae"]
collection = db["results"]


# =========================
# OCR
# =========================
def extract_text_from_pdf(pdf_path, client):
    upload = client.files.upload(
        file={
            "file_name": os.path.basename(pdf_path),
            "content": open(pdf_path, "rb")
        },
        purpose="ocr"
    )

    signed_url = client.files.get_signed_url(file_id=upload.id)

    ocr_response = client.ocr.process(
        model=OCR_MODEL,
        document={
            "type": "document_url",
            "document_url": signed_url.url
        }
    )

    return "\n".join(page.markdown for page in ocr_response.pages)


# =========================
# SIMILARITY
# =========================
def calculate_similarity(model_text, student_text):
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    emb1 = embedder.encode(model_text, convert_to_tensor=True)
    emb2 = embedder.encode(student_text, convert_to_tensor=True)

    return util.cos_sim(emb1, emb2).item()


# =========================
# EVALUATION
# =========================
def evaluate_answer(similarity):
    score = round(similarity * 100)

    if score < 45:
        return "FAIL", score, "F", (
            "Your answer does not meet the minimum requirement. "
            "Several key ideas are missing or unclear."
        )

    if score >= 90:
        return "PASS", score, "O", "Outstanding answer with excellent clarity."
    elif score >= 80:
        return "PASS", score, "A", "Very good answer. Minor improvements can make it perfect."
    elif score >= 70:
        return "PASS", score, "B+", "Good understanding shown."
    elif score >= 60:
        return "PASS", score, "B", "Basic understanding is present."
    else:
        return "PASS", score, "C", "Average answer. Important details are missing."


# =========================
# MAIN
# =========================
def main():
    student_reg_no = input("Enter Student Register Number: ").strip()

    mistral_client = Mistral(api_key=API_KEY)

    print("📄 Extracting Model Answer...")
    model_text = extract_text_from_pdf(MODEL_ANSWER_PDF, mistral_client)

    print("📝 Extracting Student Answer...")
    student_text = extract_text_from_pdf(STUDENT_ANSWER_PDF, mistral_client)

    print("📊 Calculating Similarity...")
    similarity = calculate_similarity(model_text, student_text)

    status, score, grade, feedback = evaluate_answer(similarity)

    # Store in MongoDB
    result = {
        "student_reg_no": student_reg_no,
        "score": score,
        "grade": grade,
        "status": status,
        "feedback": feedback,
        "similarity": round(similarity, 3),
        "created_at": datetime.utcnow()
    }

    collection.insert_one(result)

    # Display result
    print("\n====== RESULT ======")
    print(f"Reg No : {student_reg_no}")
    print(f"Status : {status}")
    print(f"Score  : {score}/100")
    print(f"Grade  : {grade}")
    print("Feedback:")
    print(feedback)


if __name__ == "__main__":
    main()
