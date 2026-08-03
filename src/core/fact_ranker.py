import json
import hashlib
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from src.models.domain import Fact, TargetContext, Project
from src.core.ai_gateway import AIGateway
from src.core.cache import CacheManager
from src.models.plan import ResolvedPolicies

logger = logging.getLogger(__name__)

@dataclass
class ScoredFact:
    fact: Fact
    score: float
    reasons: List[str]


class FactRanker:
    """
    Ranks project facts based on deterministic signals first (tags, metrics, priorities).
    Falls back to a semantic LLM reranker only if scores are too close or too low.
    """
    CACHE_NAMESPACE = "fact_reranker"
    PROMPT_VERSION = "reranker-v1.0"

    def __init__(self, ai_gateway: AIGateway, cache_manager: CacheManager):
        self.ai = ai_gateway
        self.cache = cache_manager

    def _deterministic_score(self, fact: Fact, target: TargetContext, policies: ResolvedPolicies) -> ScoredFact:
        score = 0.0
        reasons = []

        # 1. Metric presence (highly valued universally)
        if fact.metric:
            score += 2.0
            reasons.append("has_metric")

        # 2. Hard Skills Overlap (Target Context)
        fact_text_lower = fact.text.lower()
        tags_lower = [t.lower() for t in fact.tags]
        
        for skill in target.hard_skills:
            skill_lower = skill.lower()
            if skill_lower in tags_lower or skill_lower in fact_text_lower:
                score += 3.0
                reasons.append(f"matches_hard_skill:{skill}")

        # 3. Implied Traits Overlap
        for trait in target.implied_traits:
            trait_lower = trait.lower()
            if trait_lower in tags_lower or trait_lower in fact_text_lower:
                score += 1.5
                reasons.append(f"matches_trait:{trait}")

        # 4. Domain Priorities Overlap
        for priority in policies.active_priorities:
            pid = priority.get("id", "").lower()
            importance = priority.get("importance", "medium")
            
            # Map importance to weight
            weight = {"low": 0.5, "medium": 1.0, "high": 2.0, "critical": 3.0}.get(importance, 1.0)
            
            # Check if priority matches fact_type or tags
            if fact.fact_type.lower() == pid or pid in tags_lower or pid.replace("_", " ") in fact_text_lower:
                score += weight
                reasons.append(f"matches_priority:{pid}")
                
        # 5. Provenance (Bonus for having evidence)
        if fact.source_refs:
            score += (len(fact.source_refs) * 0.2)
            reasons.append("has_provenance")
            
        return ScoredFact(fact=fact, score=score, reasons=reasons)

    def _needs_semantic_rerank(self, scored_facts: List[ScoredFact], max_facts: int) -> bool:
        if not scored_facts:
            return False
            
        # If we have fewer facts than max, no need to rank out anything
        if len(scored_facts) <= max_facts:
            return False

        # If highest score is very low, it means deterministic failed to find overlap
        highest_score = scored_facts[0].score
        if highest_score < 2.0:
            return True
            
        # If there's a tie at the cutoff boundary
        if len(scored_facts) > max_facts:
            score_at_cutoff = scored_facts[max_facts - 1].score
            score_just_below = scored_facts[max_facts].score
            
            # If the cutoff boundary is a tight race, let the LLM decide
            if abs(score_at_cutoff - score_just_below) < 1.0:
                return True

        return False

    def _ai_rerank(self, scored_facts: List[ScoredFact], target: TargetContext, max_facts: int, mock_ai: bool = False) -> Tuple[List[Fact], str]:
        """
        Uses the AI to re-evaluate top plausible facts semantically.
        To save tokens, we only feed it the top (max_facts * 2) facts from the deterministic pass.
        """
        candidates = scored_facts[:max_facts * 2]
        
        # Sort back by original ID for deterministic caching
        candidates = sorted(candidates, key=lambda sf: sf.fact.id)
        
        payload = {
            "target_id": target.id,
            "target_desc": target.description,
            "facts": [{"id": sf.fact.id, "text": sf.fact.text} for sf in candidates],
            "version": self.PROMPT_VERSION
        }
        
        cache_key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
        
        cached_selection = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_selection and isinstance(cached_selection, list):
            fact_map = {sf.fact.id: sf.fact for sf in candidates}
            selected = [fact_map[fid] for fid in cached_selection if fid in fact_map]
            if selected:
                return selected[:max_facts], "cache_hit_reranked"

        fact_text = "\n".join([f"[{sf.fact.id}] {sf.fact.text}" for sf in candidates])
        skills_text = ", ".join(target.hard_skills) if target.hard_skills else "None explicitly stated"
        
        prompt = f"""
You are an expert technical recruiter matching candidate experiences to a Job Description.

JOB DESCRIPTION / TARGET ROLE:
{target.description}

REQUIRED SKILLS:
{skills_text}

PROJECT FACTS:
{fact_text}

TASK:
Select up to {max_facts} fact IDs that are MOST relevant to the target role. 
Look for semantic meaning (e.g. "offline validation" ≈ "resilience under failure").

RETURN FORMAT:
Return ONLY a valid JSON array of strings representing the selected fact IDs, ordered by most relevant to least relevant.
Example: ["fact_1", "fact_3", "fact_2"]
"""
        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai, model_hint="scoring")
            if mock_ai:
                selected_ids = [sf.fact.id for sf in candidates[:max_facts]]
            else:
                json_start = response_text.find('[')
                json_end = response_text.rfind(']') + 1
                if json_start != -1 and json_end != -1:
                    selected_ids = json.loads(response_text[json_start:json_end])
                else:
                    selected_ids = []
            
            if selected_ids:
                self.cache.set(self.CACHE_NAMESPACE, cache_key, selected_ids)
                
            fact_map = {sf.fact.id: sf.fact for sf in candidates}
            selected_facts = [fact_map[fid] for fid in selected_ids if fid in fact_map]
            
            if selected_facts:
                return selected_facts[:max_facts], "ai_reranked"
                
            # Parsing failed fallback
            return [sf.fact for sf in scored_facts[:max_facts]], "fallback_deterministic"
            
        except Exception as e:
            logger.error(f"Semantic reranking failed: {e}")
            return [sf.fact for sf in scored_facts[:max_facts]], "fallback_deterministic"

    def rank_facts(self, project: Project, target: TargetContext, policies: ResolvedPolicies, mock_ai: bool = False, max_facts: int = 5) -> Tuple[List[Fact], str]:
        """
        Main entry point for ranking facts.
        """
        if len(project.facts) <= max_facts:
            return project.facts, "success_unfiltered"

        # 1. Deterministic Scoring
        scored_facts = [self._deterministic_score(f, target, policies) for f in project.facts]
        
        # Sort descending by score
        scored_facts.sort(key=lambda sf: sf.score, reverse=True)
        
        # 2. Check if we need AI
        if self._needs_semantic_rerank(scored_facts, max_facts):
            logger.info(f"FactRanker: Semantic rerank triggered for project '{project.id}'.")
            return self._ai_rerank(scored_facts, target, max_facts, mock_ai=mock_ai)
            
        # 3. Fast path: Deterministic is confident
        logger.info(f"FactRanker: Deterministic ranking confident for project '{project.id}'.")
        return [sf.fact for sf in scored_facts[:max_facts]], "deterministic_confident"
