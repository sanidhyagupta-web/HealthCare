"""Build chunk metadata including source provenance and RBAC policy."""
from ingestion.chunking.semantic_chunker import Chunk
from ingestion.metadata.rbac_policy import get_allowed_roles


def build_chunk_metadata(
    chunk: Chunk,
    patient_id: str,
    source_file: str,
    department: str,
) -> dict:
    allowed_roles = get_allowed_roles(department)
    return {
        "patient_id": patient_id,
        "doc_id": chunk.doc_id,
        "chunk_id": chunk.chunk_id,
        "source_file": source_file,
        "source_page": chunk.page_number,
        "source_section": chunk.section,
        "chunk_index": chunk.chunk_index,
        "parent_chunk_id": chunk.parent_chunk_id,
        "department": department,
        "allowed_roles": allowed_roles,
    }
