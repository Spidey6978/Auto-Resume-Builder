import difflib
from typing import Tuple, Any, Optional

class MatchOutcome:
    MATCH = "MATCH"
    CONFLICT = "CONFLICT"
    NEW = "NEW"

class EntityMatcher:
    """
    Determines identity resolution between incoming entities and existing canonical entities.
    Uses deterministic text similarity scoring rather than arbitrary AI matching to remain fast and predictable.
    """
    
    @staticmethod
    def _similarity(s1: Optional[str], s2: Optional[str]) -> float:
        if not s1 and not s2: return 1.0
        if not s1 or not s2: return 0.0
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()
        return difflib.SequenceMatcher(None, s1, s2).ratio()
        
    @staticmethod
    def _date_similarity(d1_start: Optional[str], d1_end: Optional[str], d2_start: Optional[str], d2_end: Optional[str]) -> float:
        start_sim = 1.0
        if d1_start and d2_start:
            start_sim = 1.0 if d1_start.strip().lower() == d2_start.strip().lower() else 0.0
            
        end_sim = 1.0
        if d1_end and d2_end:
            end_sim = 1.0 if d1_end.strip().lower() == d2_end.strip().lower() else 0.0
            
        return (start_sim + end_sim) / 2.0
        
    @staticmethod
    def match_experience(incoming, canonical_list) -> Tuple[str, Optional[Any]]:
        best_score = 0.0
        best_match = None
        
        for canonical in canonical_list:
            org_sim = EntityMatcher._similarity(incoming.organization, canonical.organization)
            title_sim = EntityMatcher._similarity(incoming.title, canonical.title)
            date_sim = EntityMatcher._date_similarity(incoming.start_date, incoming.end_date, canonical.start_date, canonical.end_date)
            
            score = (org_sim * 0.5) + (title_sim * 0.3) + (date_sim * 0.2)
            if score > best_score:
                best_score = score
                best_match = canonical
                
        if best_score >= 0.85:
            return MatchOutcome.MATCH, best_match
        elif 0.60 <= best_score < 0.85:
            return MatchOutcome.CONFLICT, best_match
        else:
            return MatchOutcome.NEW, None

    @staticmethod
    def match_education(incoming, canonical_list) -> Tuple[str, Optional[Any]]:
        best_score = 0.0
        best_match = None
        
        for canonical in canonical_list:
            inst_sim = EntityMatcher._similarity(incoming.institution, canonical.institution)
            deg_sim = EntityMatcher._similarity(incoming.degree, canonical.degree)
            date_sim = EntityMatcher._date_similarity(incoming.start_date, incoming.end_date, canonical.start_date, canonical.end_date)
            
            score = (inst_sim * 0.5) + (deg_sim * 0.3) + (date_sim * 0.2)
            if score > best_score:
                best_score = score
                best_match = canonical
                
        if best_score >= 0.85:
            return MatchOutcome.MATCH, best_match
        elif 0.60 <= best_score < 0.85:
            return MatchOutcome.CONFLICT, best_match
        else:
            return MatchOutcome.NEW, None
            
    @staticmethod
    def match_project(incoming, canonical_list) -> Tuple[str, Optional[Any]]:
        best_score = 0.0
        best_match = None
        
        for canonical in canonical_list:
            name_sim = EntityMatcher._similarity(incoming.name, canonical.name)
            
            score = name_sim
            if score > best_score:
                best_score = score
                best_match = canonical
                
        if best_score >= 0.85:
            return MatchOutcome.MATCH, best_match
        elif 0.60 <= best_score < 0.85:
            return MatchOutcome.CONFLICT, best_match
        else:
            return MatchOutcome.NEW, None

    @staticmethod
    def match_award(incoming, canonical_list) -> Tuple[str, Optional[Any]]:
        best_score = 0.0
        best_match = None
        
        for canonical in canonical_list:
            title_sim = EntityMatcher._similarity(incoming.title, canonical.title)
            
            score = title_sim
            if score > best_score:
                best_score = score
                best_match = canonical
                
        if best_score >= 0.85:
            return MatchOutcome.MATCH, best_match
        elif 0.60 <= best_score < 0.85:
            return MatchOutcome.CONFLICT, best_match
        else:
            return MatchOutcome.NEW, None
