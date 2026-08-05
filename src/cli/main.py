import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Ensure src root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure UTF-8 stdout printing on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from core.cache import CacheManager
from core.ai_gateway import AIGateway
from core.compiler import ResumeCompiler
from adapters.github_adapter import GitHubAdapter
from adapters.registry import AdapterRegistry
from core.profile_manager import ProfileManager
from core.fact_extractor import FactExtractor
from core.generator import ContentGenerator
from core.pipeline import BuildPipeline
from core.domain_loader import DomainLoader

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Auto Resume Builder — CLI")
    parser.add_argument(
        "--sync",
        type=str,
        help="Sync a GitHub repository (format: user/repo). Example: Spidey6978/TransitOS",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the PDF resume from the canonical profile.",
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Name of a loadout in data/targets/ (e.g., 'backend')",
    )
    parser.add_argument(
        "--job",
        type=str,
        help="Path to a raw job description txt file",
    )
    parser.add_argument(
        "--mock-ai",
        action="store_true",
        help="Skip Gemini API calls and use simulated placeholder responses.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear local SQLite cache before running.",
    )
    args = parser.parse_args()

    # Configure root logging for core modules
    # We set level to WARNING by default so it doesn't spam the CLI, 
    # but captures errors/warnings from core modules.
    logging.basicConfig(
        level=logging.WARNING,
        format="  [!] %(levelname)s - %(name)s - %(message)s"
    )

    print("=========================================")
    print("        Auto Resume Builder CLI          ")
    print("=========================================")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cache_mgr = CacheManager()

    if args.clear_cache:
        print("🧹 Clearing local SQLite cache...")
        cache_mgr.clear()

    if args.mock_ai:
        print("⚠️ MOCK AI MODE: Bypassing Gemini API calls.")

    # 1. Initialize Infrastructure Components
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token and args.sync:
        print("  [!] Warning: GITHUB_TOKEN not set. Sync may fail due to rate limits.")

    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key and not args.mock_ai:
        print("  [!] Error: GEMINI_API_KEY not set in environment.")
        sys.exit(1)

    github_adapter = GitHubAdapter(token=github_token, cache_manager=cache_mgr)
    
    adapter_registry = AdapterRegistry()
    adapter_registry.register("github", github_adapter)

    ai_gateway = AIGateway(api_key=gemini_api_key)
    
    # 2. Initialize Domain Services
    extractor = FactExtractor(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    generator = ContentGenerator(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    
    canonical_path = os.path.join(base_dir, "data", "canonical_profile.yaml")
    profile_manager = ProfileManager(canonical_path)
    
    templates_dir = os.path.join(base_dir, "templates")
    compiler = ResumeCompiler(templates_dir=templates_dir)

    # Initialize KnowledgeStore
    from core.knowledge.store import KnowledgeStore
    knowledge_dir = os.path.join(base_dir, "data", "knowledge")
    knowledge_store = KnowledgeStore(knowledge_dir=knowledge_dir)

    # Initialize DomainLoader
    domains_dir = os.path.join(base_dir, "config", "domains")
    domain_loader = DomainLoader(domains_dir=domains_dir)
    print(f"🌍 Loaded {len(domain_loader.domains)} domains")

    # Initialize TargetResolver
    from core.target_resolver import JobDescriptionExtractor, TargetResolver
    extractor_service = JobDescriptionExtractor(ai_gateway=ai_gateway)
    target_resolver = TargetResolver(extractor=extractor_service, knowledge_store=knowledge_store)

    # Initialize TargetLoader
    from core.target_loader import TargetLoader
    from core.target_engine import TargetEngine
    from core.knowledge.evaluator import PolicyEvaluator
    from core.fact_ranker import FactRanker
    
    policy_evaluator = PolicyEvaluator(store=knowledge_store)
    fact_ranker = FactRanker(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    
    targets_dir = os.path.join(base_dir, "data", "targets")
    target_loader = TargetLoader(targets_dir=targets_dir, target_resolver=target_resolver)
    target_engine = TargetEngine(ai_gateway=ai_gateway, cache_manager=cache_mgr, policy_evaluator=policy_evaluator, fact_ranker=fact_ranker)

    # 3. Inject into Pipeline Orchestrator
    pipeline = BuildPipeline(
        profile_manager=profile_manager,
        adapter_registry=adapter_registry,
        extractor=extractor,
        generator=generator,
        compiler=compiler,
        target_engine=target_engine
    )

    # 4. Execute requested commands
    should_build = args.build or not args.sync

    if args.sync:
        # In a real CLI, we might parse source_type:identifier (e.g. github:Spidey6978/TransitOS)
        # For backwards compatibility with the current CLI, assume github if no prefix
        identifier = args.sync
        source_type = "github"
        if ":" in identifier:
            source_type, identifier = identifier.split(":", 1)
            
        print(f"🔄 Syncing {source_type} source: {identifier}")
        result = pipeline.sync_project(source_type=source_type, identifier=identifier, mock_ai=args.mock_ai)
        if result.success:
            print(f"  [OK] {result.message}")
        else:
            print(f"  [!] {result.message}")

    if should_build:
        print("🎯 Loading Target Context...")
        try:
            target_context = target_loader.load_target(target_name=args.target, job_path=args.job, mock_ai=args.mock_ai)
            print(f"  [OK] Targeted for: {target_context.id}")
        except Exception as e:
            print(f"  [!] Failed to load target: {e}")
            sys.exit(1)

        print("🔨 Building Resume PDF...")
        result = pipeline.build_resume(target=target_context, mock_ai=args.mock_ai)
        if result.success:
            print(f"  [OK] {result.message}")
            print(f"  📄 PDF generated at: {result.pdf_path}")
        else:
            print(f"  [!] {result.message}")

    # Display Cache Stats
    stats = cache_mgr.stats()
    print(f"📊 Cache Stats: {stats}")
    print("=========================================")


if __name__ == "__main__":
    main()
