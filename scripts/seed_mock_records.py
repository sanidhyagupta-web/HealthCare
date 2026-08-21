"""
Generate synthetic medical records and push them through the ingestion pipeline.
Creates ~20 text-based records across different departments.
"""
import sys
import uuid
import random
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import init_db
from ingestion.registry import register_document, update_status
from ingestion.state_machine import DocStatus
from app.config import settings
import queues

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEPARTMENTS = ["cardiology", "oncology", "general", "radiology"]

TEMPLATES = [
    """\
Patient Name: {name}
MRN: {mrn}
Date of Visit: {date}
Department: {dept}

## Chief Complaint
Patient presents with complaints of {complaint}.

## History Of Present Illness
{name} is a {age}-year-old patient with a history of {history}.
Symptoms began {onset} ago and have been progressively worsening.

## Medications
- {med1} {dose1}
- {med2} {dose2}

## Assessment
{assessment}

## Plan
1. Continue current medications.
2. Follow-up in {followup} weeks.
3. Order {test}.

## Follow-Up
Patient instructed to return if symptoms worsen.
Phone: {phone}
""",
    """\
DISCHARGE SUMMARY
Patient: {name}  |  MRN: {mrn}  |  DOB: {dob}
Admission: {date}  |  Department: {dept}

## Diagnosis
Primary: {diagnosis}
Secondary: {secondary}

## Procedure Notes
{procedure} was performed without complications.

## Lab Results
- WBC: {wbc} K/uL
- HGB: {hgb} g/dL
- Platelets: {plt} K/uL

## Imaging
{imaging} — {imaging_result}

## Recommendations
{name} should follow up with {specialist} within {followup} days.
Address: {address}
""",
]

NAMES = ["John Smith", "Maria Garcia", "David Chen", "Susan Lee", "Robert Kim",
         "Emily Johnson", "Michael Brown", "Sarah Wilson", "James Taylor", "Linda Martinez"]
COMPLAINTS = ["chest pain", "shortness of breath", "fatigue", "dizziness", "headache",
              "lower back pain", "joint stiffness", "persistent cough", "nausea", "palpitations"]
DIAGNOSES = ["Atrial fibrillation", "Type 2 diabetes mellitus", "Hypertension",
              "Chronic kidney disease stage 3", "Asthma", "Hypothyroidism",
              "Osteoarthritis", "Major depressive disorder"]
MEDS = [("Metformin", "500mg BID"), ("Lisinopril", "10mg daily"), ("Atorvastatin", "20mg QHS"),
        ("Aspirin", "81mg daily"), ("Levothyroxine", "50mcg daily"), ("Amlodipine", "5mg daily")]
TESTS = ["CBC with differential", "BMP", "HbA1c", "chest X-ray", "ECG", "echocardiogram"]
IMAGING = ["Chest X-Ray", "CT Abdomen", "MRI Brain", "Ultrasound Abdomen"]


def _random_record(index: int) -> tuple[str, str, dict]:
    dept = random.choice(DEPARTMENTS)
    name = random.choice(NAMES)
    mrn = f"MRN{random.randint(10000, 99999)}"
    date = f"{random.randint(1, 12):02d}/{random.randint(1, 28):02d}/2025"
    dob = f"{random.randint(1950, 1990)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    med1, dose1 = random.choice(MEDS)
    med2, dose2 = random.choice(MEDS)
    diagnosis = random.choice(DIAGNOSES)

    template = random.choice(TEMPLATES)
    text = template.format(
        name=name, mrn=mrn, date=date, dob=dob, dept=dept,
        complaint=random.choice(COMPLAINTS),
        age=random.randint(30, 80),
        history=random.choice(DIAGNOSES).lower(),
        onset=f"{random.randint(1, 30)} days",
        med1=med1, dose1=dose1, med2=med2, dose2=dose2,
        assessment=f"Patient has {diagnosis}.",
        followup=random.randint(2, 12),
        test=random.choice(TESTS),
        phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        diagnosis=diagnosis,
        secondary=random.choice(DIAGNOSES).lower(),
        procedure=f"{random.choice(['Echocardiogram', 'Colonoscopy', 'Biopsy', 'Stent placement'])}",
        wbc=round(random.uniform(4.5, 11.0), 1),
        hgb=round(random.uniform(11.0, 17.0), 1),
        plt=random.randint(150, 400),
        imaging=random.choice(IMAGING),
        imaging_result=random.choice(["No acute findings", "Mild cardiomegaly", "Infiltrate present", "Normal"]),
        specialist=random.choice(["cardiologist", "endocrinologist", "pulmonologist", "neurologist"]),
        address=f"{random.randint(100, 999)} Main St, Springfield",
    )

    patient_id = f"P{random.randint(1000, 9999)}"
    meta = {"patient_id": patient_id, "department": dept}
    filename = f"record_{index:04d}_{dept}.txt"
    return text, filename, meta


def seed(n: int = 20, uploader_id: str = "seeder"):
    init_db()

    raw_dir = settings.raw_dir / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Seeding %d mock records...", n)
    for i in range(n):
        text, filename, meta = _random_record(i)
        file_path = raw_dir / filename
        file_path.write_text(text, encoding="utf-8")

        doc_id = str(uuid.uuid4())
        register_document(doc_id, filename, str(file_path), uploader_id=uploader_id)
        update_status(doc_id, DocStatus.VALIDATED)

        queues.parsing_queue.put({
            "doc_id": doc_id,
            "raw_path": str(file_path),
            "original_filename": filename,
            "uploader_id": uploader_id,
            "patient_id": meta["patient_id"],
            "department": meta["department"],
            "retry_count": 0,
        })
        logger.info("Queued doc %s (%s)", doc_id[:8], filename)

    logger.info("Seeding complete. %d documents queued.", n)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    seed(n)
