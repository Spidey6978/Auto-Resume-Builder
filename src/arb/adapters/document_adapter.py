import hashlib
from pathlib import Path
from typing import Dict, Any, List
import pypdf

from arb.adapters.base import BaseAdapter
from arb.models.domain import SourceResult, SourceStatus, EvidenceItem, SourceRef

class DocumentAdapter(BaseAdapter):
    """
    Adapter for parsing local documents (PDFs, TXT, MD) into SourceResults.
    Provides precise content hashes for provenance identity and extracts page-aware metadata.
    Does NOT contain semantic resume logic.
    """
    
    def ingest(self, identifier: str, **kwargs) -> SourceResult:
        path = Path(identifier)
        if not path.exists():
            return SourceResult(
                source_type="document",
                source_id=identifier,
                status=SourceStatus.FAILED,
                metadata={"error": f"File not found: {identifier}"}
            )
            
        try:
            file_bytes = path.read_bytes()
        except Exception as e:
            return SourceResult(
                source_type="document",
                source_id=identifier,
                status=SourceStatus.FAILED,
                metadata={"error": f"Failed to read file: {e}"}
            )
            
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        source_id = f"document:{sha256_hash}"
        
        evidence: List[EvidenceItem] = []
        
        if path.suffix.lower() == ".pdf":
            try:
                reader = pypdf.PdfReader(path)
                total_chars = 0
                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        total_chars += len(text.strip())
                        evidence.append(
                            EvidenceItem(
                                id=f"{source_id}/page/{i+1}",
                                kind="document_text",
                                content=text,
                                metadata={"page": i+1, "source_format": "pdf"},
                                provenance=SourceRef(type="document", id=source_id)
                            )
                        )
                        
                # Validation heuristic: If a PDF parses successfully but yields almost no text,
                # it's likely a scanned image (requires OCR) or has bizarre encoding.
                if total_chars < 50:
                    return SourceResult(
                        source_type="document",
                        source_id=source_id,
                        status=SourceStatus.FAILED,
                        metadata={"error": "PDF extraction yielded very little text. Is this a scanned image? ARB does not currently support OCR."}
                    )
            except Exception as e:
                return SourceResult(
                    source_type="document",
                    source_id=source_id,
                    status=SourceStatus.FAILED,
                    metadata={"error": f"Failed to parse PDF: {e}"}
                )
        elif path.suffix.lower() in [".txt", ".md"]:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if len(text.strip()) < 10:
                return SourceResult(
                    source_type="document",
                    source_id=source_id,
                    status=SourceStatus.FAILED,
                    metadata={"error": "Text file is nearly empty."}
                )
            evidence.append(
                EvidenceItem(
                    id=f"{source_id}/full",
                    kind="document_text",
                    content=text,
                    metadata={"page": 1, "source_format": path.suffix.lower()[1:]},
                    provenance=SourceRef(type="document", id=source_id)
                )
            )
        else:
            return SourceResult(
                source_type="document",
                source_id=source_id,
                status=SourceStatus.FAILED,
                metadata={"error": f"Unsupported file format: {path.suffix}"}
            )
            
        return SourceResult(
            source_type="document",
            source_id=source_id,
            evidence=evidence,
            status=SourceStatus.SUCCESS
        )
