# Auto Resume Builder — Ideas & Backlog

This file is the parking lot for ideas that are worth preserving but are **not part of the current milestone**. Its purpose is to prevent useful ideas from disappearing while also preventing feature creep from hijacking the active roadmap.

## Guiding Principle

Build the smallest complete version of the current phase first. Ideas below should move into the roadmap only when an upcoming phase actually requires them or real usage exposes the problem they solve.

---

## Multi-Source Profile Ingestion

### Existing Resume / CV Import
Use an uploaded PDF/DOCX as a universal onboarding source. Extract candidate entities and facts, show proposed profile changes for review, then merge accepted information into the Canonical Profile with provenance.

### GitHub Evidence v2
Stop treating the README as the repository itself. Build repository evidence from multiple cheap signals:
- repository metadata and description
- selected/default branch
- branch activity and divergence
- README from the selected branch
- language statistics
- directory structure
- dependency/config manifests (`pyproject.toml`, `package.json`, `pubspec.yaml`, etc.)

Later, only if necessary, consider selective source-code inspection and commit-history analysis. Avoid turning this into a general-purpose code-understanding agent prematurely.

### Evidence Model
Consider replacing the single `SourceResult.raw_content` worldview with structured evidence items, e.g. `EvidenceItem(kind, content, metadata)`. A source can then contribute multiple independently traceable pieces of evidence.

### Additional Sources
Potential adapters include:
- LinkedIn exports
- manual input
- personal websites / portfolios
- ORCID / academic publication sources
- other domain-specific exports/APIs where access and terms permit

Manual input must remain first-class; information does not need to exist online to be valid career evidence.

---

## Domain-Aware Product Experience

### Domain / Stream-Aware Onboarding
Give users a domain-aware onboarding experience (Engineering, Business/Consulting, Academic/Research, Creative/Design, General/Unsure) while keeping a **single shared engine** underneath.

The selected background/target can influence:
- recommended data sources
- relevant profile entity types
- onboarding questions
- default document type
- TargetKnowledge composition

Do not create separate codebases/products per stream.

### Background vs Application Target
Keep the user's background separate from the role they are applying for. An engineering student may target consulting, research, product, etc. Application target should generally drive document strategy more strongly than degree/background.

### DomainConfig / OnboardingProfile
Potential configuration abstraction containing display metadata, suggested sources, relevant entity types, default document type, and onboarding questions. Domain differences should be configuration/data-driven wherever possible rather than scattered `if domain == ...` branches.

### Expand Canonical Ontology from Real Requirements
Current entities are engineering-oriented. Potential future entities include publications, research, grants, teaching, certifications, portfolio work, case studies, exhibitions, commissions, etc. Add these only when implementing/testing real domains rather than predicting the entire ontology upfront.

Academic/research CVs are a strong second-domain stress test because they violate many engineering-resume assumptions (page limits, ATS emphasis, section hierarchy, publications/research prominence).

---

## User Preferences & Supervision

### Entity Priority
Allow optional coarse user preference on profile entities:
- Featured
- Normal
- Low priority
- Exclude / Never include

Avoid forcing users to manually rank every entity. User preference should influence targeting, not replace JD relevance or researched hiring priorities.

### Editable Resume Plan
Future UI should expose the structured `ResumePlan` before final generation so users can pin/hide/reorder content, change page targets, choose alternatives, and override automatic decisions without requiring a chatbot interface.

### Explainability
Expose why content was selected or removed (JD relevance, user preference, evidence strength, hiring priority, page budget). Avoid opaque model-only scores where deterministic signals can provide explanations.

---

## Content Budgeting Enhancements

### Variable Entity Budgets
Do not assume every project/experience deserves the same number of bullets. Allocate more space to stronger/relevant entities and less to weaker ones.

### Evidence Aggregation
Multiple semantically related facts about the same accomplishment may eventually be rendered as one stronger bullet carrying multiple `source_fact_ids`. Do not merge unrelated weak facts merely to save space.

### Representation Modes
Potential entity representations:
- FULL
- COMPACT
- OMITTED

Compact representations could support domain-appropriate sections such as `Additional Projects`, `Selected Publications`, or similar. Only implement after real page-fitting behavior demonstrates the need.

### Relative Ranking / Tie Handling
Avoid universal relevance thresholds that can erase candidates with generally lower scores. Prefer relative tiers and deterministic tie-breakers such as user preference, evidence strength, unique skill coverage, diversity, and relevant recency.

### Smarter Overflow Resolution
Current compile-measure-trim loop is the V1. Future resolver may consider the cost/value of removing an entire entity versus individual bullets and reallocate recovered space to stronger content. Formatting compression should remain secondary to removing low-value content.

---

## AI & Ranking Evolution

### Deterministic-First Ranking
Keep fact ranking deterministic wherever structured signals are sufficient. Use AI only for semantic ambiguity/reranking rather than making one model call per project by default.

### Semantic Similarity / Embeddings
Potential future replacement/augmentation for LLM reranking: embeddings + similarity between candidate evidence and job requirements. Only investigate after measuring actual ranking failures and AI cost.

### Provider Flexibility
Long-term AI provider abstraction may support hosted APIs, user-supplied credentials, or locally/self-hosted models for CLI users. Do not build provider complexity before deployment/cost requirements justify it.

---

## Web Product & Scaling

### Web UI
After the core engine and ingestion pipeline are stable, build a simple web UI for profile creation, source uploads, review/editing, target selection, resume-plan supervision, previews, and generation.

### Multi-Tenant / Cloud Concerns
Already keep builds isolated and dependencies injectable. Future deployment work may include authentication, persistent profile storage, per-user credentials/usage, quotas, billing, and event/progress streaming.

### Usage & Cost Telemetry
Before optimizing AI economics, measure per-build model calls, token usage where available, cache-hit rate, latency, and failure/retry behavior. Use actual usage data before choosing quotas or monetization.

### Monetization
Keep revenue model undecided during development. Possibilities previously discussed include free allowances, usage-based credits/markup, subscriptions, BYOK, and combinations thereof. Decide using real cost and usage data rather than locking the architecture to one model now.

---

## Research / TargetKnowledge

### Knowledge Refresh Pipeline
Research-backed TargetKnowledge may eventually be periodically refreshed from authoritative career services, employer/recruiting reports, and domain-specific sources. Preserve claim-level provenance and disputes rather than blindly replacing older guidance.

### Policy Typing
`recommendation: Dict[str, Any]` remains intentionally flexible while the ontology is being discovered. Consider typed common policies only after enough substantially different domains reveal a stable vocabulary.

### Dynamic / Unknown Targets
For roles absent from the knowledge bank, eventually combine permanent researched domain knowledge with dynamic analysis of the supplied job description rather than attempting to pre-store every job title in existence.

---

## Explicitly Deferred Rabbit Holes

Do **not** implement these merely because they are technically interesting:
- exhaustive repository/codebase understanding
- AST/call-graph analysis for GitHub ingestion
- automatic scanning of every Git branch
- complex pixel-perfect page optimization
- giant universal career ontology upfront
- self-hosted cloud LLM infrastructure before economics justify it
- Redis/Celery/distributed infrastructure without demonstrated workload
- automatic research-refresh daemons before TargetKnowledge usage stabilizes

Promote one of these only when real requirements or measurements justify it.
