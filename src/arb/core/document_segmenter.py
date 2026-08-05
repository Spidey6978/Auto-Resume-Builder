import json
import hashlib
import logging
import yaml
from pathlib import Path
from typing import List, Dict, Optional

from arb.models.domain import EvidenceItem
from arb.core.ai_gateway import AIGateway
from arb.core.cache import CacheManager
from arb.core.paths import get_bundled_data_dir

logger = logging.getLogger(__name__)

class DocumentSegmenter:
    """
    Splits raw document text into semantic evidence blocks (experience, education, projects, skills).
    Uses deterministic heuristics based on common resume headings. 
    Falls back to LLM-based segmentation if heuristics yield low confidence.
    """

    def __init__(self, ai_gateway: AIGateway, cache_manager: Optional[CacheManager] = None):
        self.ai_gateway = ai_gateway
        self.cache_manager = cache_manager
        
        self.known_sections = {}
        headings_path = get_bundled_data_dir() / "data" / "knowledge" / "known_headings.yaml"
        if headings_path.exists():
            try:
                with open(headings_path, "r", encoding="utf-8") as f:
                    self.known_sections = yaml.safe_load(f) or {}
            except Exception:
                pass

    def segment(self, evidence_items: List[EvidenceItem]) -> List[EvidenceItem]:
        """
        Takes raw document_text evidence items and partitions them into semantic blocks.
        """
        doc_texts = [item.content for item in evidence_items if item.kind == "document_text"]
        if not doc_texts:
            return []
            
        full_text = "\n\n".join(doc_texts)
        
        # Stage A: Heuristic segmentation
        blocks = self._heuristic_segment(full_text)
        
        # Stage B: Fallback
        # If we didn't find at least 2 distinct semantic sections, heuristics likely failed to find headers.
        semantic_count = len([b for b in blocks if b["type"] not in ("unknown",)])
        if semantic_count < 2:
            blocks = self._llm_segment(full_text)
            
        segmented_evidence = []
        base_provenance = evidence_items[0].provenance if evidence_items else None
        
        for i, block in enumerate(blocks):
            if not block["content"].strip():
                continue
            segmented_evidence.append(
                EvidenceItem(
                    id=f"{base_provenance.id if base_provenance else 'doc'}/block/{i}",
                    kind=f"{block['type']}_block",
                    content=block["content"],
                    metadata={"segmentation_method": block.get("method", "heuristic")},
                    provenance=base_provenance
                )
            )
            
        return segmented_evidence

    def _heuristic_segment(self, text: str) -> List[Dict[str, str]]:
        lines = text.split("\n")
        
        blocks = []
        current_type = "unknown"
        current_content = []
        
        for line in lines:
            stripped = line.strip()
            # Ignore empty lines for header detection
            if not stripped:
                current_content.append(line)
                continue
                
            # Normalize whitespace for comparison
            normalized = " ".join(stripped.split()).upper()
            
            matched_type = None
            for sec_type, aliases in self.known_sections.items():
                if normalized in aliases:
                    matched_type = sec_type
                    break
                        
            if matched_type:
                if current_content:
                    blocks.append({"type": current_type, "content": "\n".join(current_content), "method": "heuristic"})
                current_type = matched_type
                current_content = [line]
            else:
                current_content.append(line)
                
        if current_content:
            blocks.append({"type": current_type, "content": "\n".join(current_content), "method": "heuristic"})
            
        return blocks

    def _llm_segment(self, text: str) -> List[Dict[str, str]]:
        prompt = (
            "You are an expert resume parser. I will provide the raw text of a resume. "
            "Please segment the text into logical sections based on the content.\n"
            "Use ONLY these exact section types: 'experience', 'education', 'projects', 'skills', 'awards', or 'unknown' (for header/summary/objective).\n"
            "Respond ONLY with a valid JSON array of objects. Each object must have a 'type' and 'content' (the exact raw text belonging to that section).\n\n"
            f"RESUME TEXT:\n{text}\n"
        )
        
        hash_val = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = f"segment_{hash_val}"
        if self.cache_manager:
            cached = self.cache_manager.get("document_segmentation", cache_key)
            if cached:
                return cached
                
        try:
            response = self.ai_gateway.generate_text(prompt)
            start = response.find("[")
            end = response.rfind("]")
            if start != -1 and end != -1:
                json_str = response[start:end+1]
            else:
                raise ValueError("No JSON array found in LLM response.")
                
            blocks = json.loads(json_str)
            for b in blocks:
                b["method"] = "llm_fallback"
                
            if self.cache_manager:
                self.cache_manager.set("document_segmentation", cache_key, blocks)
                
            return blocks
        except Exception as exc:
            logger.warning("Document segmentation failed during LLM fallback: %s", exc, exc_info=True)
            return [{"type": "unknown", "content": text, "method": "llm_fallback_failed"}]
