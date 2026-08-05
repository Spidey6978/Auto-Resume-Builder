import logging
from typing import List
from arb.models.domain import CanonicalProfile, Project, ExperienceItem, EducationItem, AwardItem
from arb.core.evidence_extractor import EntityExtractionResult
from arb.core.entity_matcher import EntityMatcher, MatchOutcome

logger = logging.getLogger(__name__)

class ProfileMerger:
    """
    Safely merges extracted entities into the CanonicalProfile based on EntityMatcher classifications.
    Enforces the rule: Ingestion may add information automatically. It may not destructively replace 
    conflicting canonical information without sufficient evidence.
    """
    def __init__(self, profile: CanonicalProfile):
        self.profile = profile
        self.matcher = EntityMatcher()

    def merge(self, extraction_result: EntityExtractionResult) -> None:
        self._merge_experience(extraction_result.experience)
        self._merge_education(extraction_result.education)
        self._merge_projects(extraction_result.projects)
        self._merge_awards(extraction_result.awards)
        self._merge_skills(extraction_result.skills)
        
    def _merge_experience(self, incoming_items: List[ExperienceItem]):
        for inc in incoming_items:
            outcome, match = self.matcher.match_experience(inc, self.profile.experience)
            if outcome == MatchOutcome.NEW:
                self.profile.experience.append(inc)
            elif outcome == MatchOutcome.MATCH:
                # Merge missing fields
                if not match.location and inc.location: match.location = inc.location
                if not match.end_date and inc.end_date: match.end_date = inc.end_date
            elif outcome == MatchOutcome.CONFLICT:
                logger.warning(f"Conflict detected for experience '{inc.organization}'. Canonical preserved.")
                
    def _merge_education(self, incoming_items: List[EducationItem]):
        for inc in incoming_items:
            outcome, match = self.matcher.match_education(inc, self.profile.education)
            if outcome == MatchOutcome.NEW:
                self.profile.education.append(inc)
            elif outcome == MatchOutcome.MATCH:
                if not match.location and inc.location: match.location = inc.location
                if not match.field and inc.field: match.field = inc.field
            elif outcome == MatchOutcome.CONFLICT:
                logger.warning(f"Conflict detected for education '{inc.institution}'. Canonical preserved.")
                
    def _merge_projects(self, incoming_items: List[Project]):
        for inc in incoming_items:
            outcome, match = self.matcher.match_project(inc, self.profile.projects)
            if outcome == MatchOutcome.NEW:
                self.profile.projects.append(inc)
            elif outcome == MatchOutcome.MATCH:
                if not match.link and inc.link: match.link = inc.link
                # Merge tech stack order-preserving without duplicates
                match.tech_stack = list(dict.fromkeys(match.tech_stack + inc.tech_stack))
            elif outcome == MatchOutcome.CONFLICT:
                logger.warning(f"Conflict detected for project '{inc.name}'. Canonical preserved.")
                
    def _merge_awards(self, incoming_items: List[AwardItem]):
        for inc in incoming_items:
            outcome, match = self.matcher.match_award(inc, self.profile.awards)
            if outcome == MatchOutcome.NEW:
                self.profile.awards.append(inc)
            elif outcome == MatchOutcome.MATCH:
                if not match.organization and inc.organization: match.organization = inc.organization
                if not match.event and inc.event: match.event = inc.event
                if not match.year and inc.year: match.year = inc.year
            elif outcome == MatchOutcome.CONFLICT:
                logger.warning(f"Conflict detected for award '{inc.title}'. Canonical preserved.")
                
    def _merge_skills(self, incoming_skills: dict):
        for cat, items in incoming_skills.items():
            if cat not in self.profile.skills:
                self.profile.skills[cat] = []
            # Merge skills order-preserving
            self.profile.skills[cat] = list(dict.fromkeys(self.profile.skills[cat] + items))
