import json
import hashlib
import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

from models.domain import Fact, SourceResult, SourceStatus
from core.ai_gateway import AIGateway
from core.cache import CacheManager


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    NO_FACTS = "no_facts"
    INVALID_RESPONSE = "invalid_response"
    INSUFFICIENT_SOURCE = "insufficient_source"
    AI_ERROR = "ai_error"


@dataclass
class ExtractionResult:
    facts: List[Fact]
    status: ExtractionStatus
    error: Optional[str] = None


class FactExtractor:
    """
    Extracts atomic Fact domain objects from raw SourceResult payloads using AIGateway.
    """
    CACHE_NAMESPACE = "llm_facts"
    PROMPT_VERSION = "extract-v1.0"

    def __init__(self, ai_gateway: Optional[AIGateway] = None, cache_manager: Optional[CacheManager] = None):
        self.ai = ai_gateway or AIGateway()
        self.cache = cache_manager or CacheManager()

    def _fingerprint(self, source_result: SourceResult) -> str:
        prompt_hash = CacheManager.hash_key(self.PROMPT_VERSION)
        content_hash = CacheManager.hash_key(source_result.raw_content)
        return f"{self.PROMPT_VERSION}||{prompt_hash}||{source_result.source_id}||{content_hash}"

    def _generate_fact_id(self, entity_id: str, fact_type: str, text: str) -> str:
        normalized = re.sub(r'\W+', '', text.lower())
        short_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:6]
        # Clean entity_id (e.g. github:Spidey6978/TransitOS -> transitos)
        clean_id = re.sub(r'\W+', '_', entity_id.split("/")[-1].lower())
        clean_type = re.sub(r'\W+', '_', fact_type.lower())
        return f"{clean_id}-{clean_type}-{short_hash}"

    def _clean_json_response(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def extract(self, source: SourceResult, entity_id: str, mock_ai: bool = False) -> ExtractionResult:
        """
        Extracts facts from a source result using Gemini LLM.
        Applies a strict extraction prompt and enforces standard JSON schema.
        """
        if source.status != SourceStatus.SUCCESS or not source.raw_content or len(source.raw_content.strip()) < 50:
            return ExtractionResult(facts=[], status=ExtractionStatus.INSUFFICIENT_SOURCE)

        cache_key = self._fingerprint(source)
        cached = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached is not None and isinstance(cached, list):
            # Reconstruct Fact objects from cached dicts
            try:
                facts = [Fact.from_dict(f) for f in cached]
                return ExtractionResult(facts=facts, status=ExtractionStatus.SUCCESS)
            except Exception:
                pass  # Fall through to re-extract if cache format changed

        prompt = f"""
        Extract atomic, technically meaningful facts explicitly supported by the provided source material.
        Facts describe what the system does or how it is implemented; they are not resume bullets.
        Do not use promotional language (e.g., "architected a groundbreaking", "spearheaded").
        Do not infer technologies, metrics, performance characteristics, architecture, or outcomes not explicitly supported by the source.
        Each fact should represent one independently useful claim.
        Quantitative metrics must appear explicitly in the source; otherwise metric MUST be null.

        Output ONLY a JSON array of objects with the following schema:
        [
          {{
            "text": "Fact statement (boring and objective).",
            "fact_type": "architecture | performance | math_physics | implementation | general",
            "metric": "verbatim quantitative string or null",
            "tags": ["tech1", "tech2"]
          }}
        ]

        Source Material:
        {source.raw_content[:40000]}
        """

        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai, model_hint=entity_id)
        except Exception as e:
            return ExtractionResult(facts=[], status=ExtractionStatus.AI_ERROR, error=str(e))

        cleaned_json = self._clean_json_response(response_text)
        try:
            parsed_array = json.loads(cleaned_json)
            if not isinstance(parsed_array, list):
                raise ValueError("LLM response is not a JSON array")
        except Exception as e:
            return ExtractionResult(facts=[], status=ExtractionStatus.INVALID_RESPONSE, error=str(e))

        facts = []
        source_ref = f"{source.source_type}:{source.source_id}"
        
        for item in parsed_array:
            try:
                text = item["text"]
                if not isinstance(text, str) or not text.strip():
                    continue
                fact_type = item.get("fact_type", "general")
                metric = item.get("metric")
                tags = item.get("tags", [])
                
                fact_id = self._generate_fact_id(entity_id, fact_type, text)
                fact = Fact(
                    id=fact_id,
                    text=text,
                    fact_type=fact_type,
                    metric=metric,
                    tags=tags,
                    source_refs=[source_ref]
                )
                facts.append(fact)
            except KeyError:
                continue

        if not facts:
            return ExtractionResult(facts=[], status=ExtractionStatus.NO_FACTS)

        self.cache.set(self.CACHE_NAMESPACE, cache_key, [f.to_dict() for f in facts])
        return ExtractionResult(facts=facts, status=ExtractionStatus.SUCCESS)
