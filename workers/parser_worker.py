"""
Parser/OCR Worker
Downloads raw file from S3 → detects doc type → extracts text →
uploads parsed text back to S3 → pushes to markdown_queue.

Raw file is downloaded to a temp file, processed, then immediately deleted.
No plaintext PII ever persists on local disk.
"""
import logging
import os
from pathlib import Path
from workers.base_worker import BaseWorker
from ingestion.parsers.doc_type_detector import detect_doc_type
from ingestion.parsers.dicom_parser import parse_dicom
from ingestion.parsers.pdf_parser import parse_typed_pdf
from ingestion.parsers.text_parser import parse_text_file
from ingestion.ocr.tesseract_ocr import run_ocr
from ingestion.ocr.ocr_quality import is_quality_sufficient, correct_medical_terms
from ingestion.registry import update_status
from ingestion.state_machine import DocStatus
from storage.s3_client import download_to_tempfile, upload
import queues

logger = logging.getLogger(__name__)

DOC_TYPED_PDF = "pdf_typed"
DOC_SCANNED_PDF = "pdf_scanned"
DOC_TEXT = "text"
DOC_DICOM = "dicom"


class ParserWorker(BaseWorker):
    def __init__(self):
        super().__init__("ParserWorker", queues.parsing_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        raw_s3_key = message["raw_s3_key"]
        suffix = message.get("file_suffix", ".pdf")
        original_filename = message.get("original_filename", "")

        # Download encrypted raw file to a temp file — deleted in finally block
        tmp_path = download_to_tempfile(raw_s3_key, suffix=suffix)
        try:
            detector_name = original_filename or Path(tmp_path).name
            dicom_bytes = Path(tmp_path).read_bytes() if detector_name.lower().endswith(".dcm") else None
            doc_type = detect_doc_type(detector_name, file_bytes=dicom_bytes)
            update_status(doc_id, DocStatus.PARSING, file_type=doc_type)

            if doc_type == DOC_DICOM:
                parsed = parse_dicom(dicom_bytes if dicom_bytes is not None else Path(tmp_path).read_bytes())
                full_text = parsed["text"]
                page_texts = [(1, full_text)]

            elif doc_type == DOC_TYPED_PDF:
                parsed = parse_typed_pdf(tmp_path, doc_id)
                if parsed.full_text.strip():
                    full_text = parsed.full_text
                    page_texts = [(p.page_number, p.text) for p in parsed.pages]
                else:
                    # OCR fallback for image-only PDFs misclassified as typed.
                    doc_type = DOC_SCANNED_PDF
                    ocr_result = run_ocr(tmp_path, doc_id)
                    if not is_quality_sufficient(ocr_result):
                        update_status(doc_id, DocStatus.FAILED, error_message="OCR quality below threshold")
                        self.input_queue.send_to_dlq(message, reason="OCR quality insufficient")
                        return
                    for page in ocr_result.pages:
                        page.text = correct_medical_terms(page.text)
                    full_text = ocr_result.full_text
                    page_texts = [(p.page_number, p.text) for p in ocr_result.pages]

            elif doc_type == DOC_SCANNED_PDF:
                ocr_result = run_ocr(tmp_path, doc_id)
                if not is_quality_sufficient(ocr_result):
                    update_status(doc_id, DocStatus.FAILED, error_message="OCR quality below threshold")
                    self.input_queue.send_to_dlq(message, reason="OCR quality insufficient")
                    return
                for page in ocr_result.pages:
                    page.text = correct_medical_terms(page.text)
                full_text = ocr_result.full_text
                page_texts = [(p.page_number, p.text) for p in ocr_result.pages]

            else:  # text
                parsed = parse_text_file(tmp_path, doc_id)
                full_text = parsed.full_text
                page_texts = [(p.page_number, p.text) for p in parsed.pages]

        finally:
            os.unlink(tmp_path)

        # Upload extracted plaintext to S3 (still pre-markdown, still contains PII)
        parsed_s3_key = f"processed/{doc_id}/raw.txt"
        upload(parsed_s3_key, full_text)

        update_status(doc_id, DocStatus.PARSED, file_type=doc_type)

        queues.markdown_queue.put({
            **message,
            "doc_type": doc_type,
            "parsed_s3_key": parsed_s3_key,
            "page_texts": page_texts,
        })
