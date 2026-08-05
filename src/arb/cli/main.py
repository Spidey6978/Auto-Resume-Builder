import os
import sys
import argparse
import logging
import platform
import subprocess
from dotenv import load_dotenv

# Ensure UTF-8 stdout printing on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from arb.core.paths import get_user_data_dir, get_bundled_data_dir

# Load environment variables from the user data dir if it exists there
env_path = get_user_data_dir() / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

def init_services(args):
    """Initializes and returns the BuildPipeline and related dependencies."""
    from arb.core.cache import CacheManager
    from arb.core.ai_gateway import AIGateway
    from arb.core.compiler import ResumeCompiler
    from arb.adapters.github_adapter import GitHubAdapter
    from arb.adapters.registry import AdapterRegistry
    from arb.core.profile_manager import ProfileManager
    from arb.core.fact_extractor import FactExtractor
    from arb.core.generator import ContentGenerator
    from arb.core.pipeline import BuildPipeline
    from arb.core.domain_loader import DomainLoader
    from arb.core.target_resolver import JobDescriptionExtractor, TargetResolver
    from arb.core.target_loader import TargetLoader
    from arb.core.target_engine import TargetEngine
    from arb.core.knowledge.evaluator import PolicyEvaluator
    from arb.core.fact_ranker import FactRanker
    from arb.core.knowledge.store import KnowledgeStore

    cache_mgr = CacheManager()
    
    mock_ai = getattr(args, "mock_ai", False)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key and not mock_ai:
        print("  [!] Error: GEMINI_API_KEY not set in environment or .env file.")
        print("      Run 'arb init' to set up your environment.")
        sys.exit(1)

    ai_gateway = AIGateway(api_key=gemini_api_key)
    
    github_token = os.getenv("GITHUB_TOKEN")
    github_adapter = GitHubAdapter(token=github_token, cache_manager=cache_mgr)
    
    adapter_registry = AdapterRegistry()
    adapter_registry.register("github", github_adapter)

    extractor = FactExtractor(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    generator = ContentGenerator(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    
    canonical_path = get_user_data_dir() / "canonical_profile.yaml"
    if not canonical_path.exists():
        print(f"  [!] Canonical profile not found at {canonical_path}")
        print("      Run 'arb init' to set up your profile.")
        sys.exit(1)
        
    profile_manager = ProfileManager(str(canonical_path))
    
    templates_dir = get_bundled_data_dir() / "templates"
    compiler = ResumeCompiler(templates_dir=str(templates_dir))
    
    knowledge_dir = get_bundled_data_dir() / "data" / "knowledge"
    knowledge_store = KnowledgeStore(knowledge_dir=str(knowledge_dir))

    domains_dir = get_bundled_data_dir() / "config" / "domains"
    domain_loader = DomainLoader(domains_dir=str(domains_dir))
    
    extractor_service = JobDescriptionExtractor(ai_gateway=ai_gateway)
    target_resolver = TargetResolver(extractor=extractor_service, knowledge_store=knowledge_store, domain_loader=domain_loader)
    
    policy_evaluator = PolicyEvaluator(store=knowledge_store)
    fact_ranker = FactRanker(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    
    targets_dir = get_bundled_data_dir() / "data" / "targets"
    target_loader = TargetLoader(targets_dir=str(targets_dir), target_resolver=target_resolver)
    target_engine = TargetEngine(
        ai_gateway=ai_gateway, 
        cache_manager=cache_mgr, 
        policy_evaluator=policy_evaluator, 
        fact_ranker=fact_ranker, 
        domain_loader=domain_loader
    )

    pipeline = BuildPipeline(
        profile_manager=profile_manager,
        adapter_registry=adapter_registry,
        extractor=extractor,
        generator=generator,
        compiler=compiler,
        target_engine=target_engine,
        domain_loader=domain_loader
    )
    
    return pipeline, target_loader, cache_mgr


def handle_init(args):
    print("🚀 Initializing Auto Resume Builder...")
    data_dir = get_user_data_dir()
    print(f"User data directory: {data_dir}")
    
    # Check for legacy canonical profile in repo (if running from source)
    legacy_path = Path.cwd() / "data" / "canonical_profile.yaml"
    canonical_path = data_dir / "canonical_profile.yaml"
    
    if not canonical_path.exists():
        if legacy_path.exists():
            print("Found legacy canonical_profile.yaml. Migrating to user data directory...")
            import shutil
            shutil.copy(legacy_path, canonical_path)
            print("Migration complete.")
        else:
            print("Creating empty canonical_profile.yaml...")
            canonical_path.write_text("personal:\n  name: ''\nexperience: []\nprojects: []\neducation: []\nskills: []\n", encoding="utf-8")
    
    env_file = data_dir / ".env"
    if not env_file.exists():
        print("\nAPI Configuration")
        key = input("Enter your Google Gemini API Key (or press enter to skip): ").strip()
        github = input("Enter your GitHub Token (optional, for rate limits): ").strip()
        
        lines = []
        if key: lines.append(f"GEMINI_API_KEY={key}")
        if github: lines.append(f"GITHUB_TOKEN={github}")
        
        env_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"Saved configuration to {env_file}")
        
    print("\n✅ Initialization complete. Try running 'arb doctor' or 'arb build'.")


def handle_doctor(args):
    print("🩺 ARB Doctor")
    print("-" * 30)
    
    # Python
    print(f"✓ Python {platform.python_version()}")
    
    # Data Dir
    data_dir = get_user_data_dir()
    if data_dir.exists() and os.access(data_dir, os.W_OK):
        print(f"✓ User data directory ({data_dir})")
    else:
        print(f"✗ User data directory is missing or not writable: {data_dir}")
        
    # Profile
    prof = data_dir / "canonical_profile.yaml"
    if prof.exists():
        print("✓ Canonical profile found")
    else:
        print("✗ Canonical profile missing (run 'arb init')")
        
    # Keys
    if os.getenv("GEMINI_API_KEY"):
        print("✓ GEMINI_API_KEY found")
    else:
        print("✗ GEMINI_API_KEY not set")
        
    if os.getenv("GITHUB_TOKEN"):
        print("✓ GitHub token found")
    else:
        print("! GitHub token not set (public repos only, rate limits apply)")
        
    # LuaLaTeX
    import shutil
    if shutil.which("lualatex"):
        print("✓ LuaLaTeX compiler found")
    elif shutil.which("tectonic"):
        print("✓ Tectonic compiler found")
    else:
        print("✗ No LaTeX compiler (LuaLaTeX or Tectonic) found in PATH")
        
    print("-" * 30)
    print("Ready to build." if os.getenv("GEMINI_API_KEY") else "Not ready.")


def handle_build(args):
    pipeline, target_loader, cache_mgr = init_services(args)
    
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
        if args.output:
            import shutil
            shutil.copy(result.pdf_path, args.output)
            print(f"  📄 Copied to: {args.output}")
    else:
        print(f"  [!] {result.message}")
        
    # Display Cache Stats
    stats = cache_mgr.stats()
    print(f"📊 Cache Stats: {stats}")


def handle_source(args):
    if args.source_cmd == "add":
        if args.type == "github":
            pipeline, _, _ = init_services(args)
            print(f"🔄 Syncing github source: {args.identifier}")
            result = pipeline.sync_project(source_type="github", identifier=args.identifier, mock_ai=args.mock_ai)
            if result.success:
                print(f"  [OK] {result.message}")
            else:
                print(f"  [!] {result.message}")
        else:
            print(f"Source type '{args.type}' not fully supported yet.")
    elif args.source_cmd == "list":
        print("Source listing coming soon.")


def handle_profile(args):
    prof = get_user_data_dir() / "canonical_profile.yaml"
    if args.profile_cmd == "path":
        print(prof)
    elif args.profile_cmd == "show":
        if prof.exists():
            print(prof.read_text(encoding="utf-8"))
        else:
            print("Profile not found.")
    elif args.profile_cmd == "edit":
        if not prof.exists():
            print("Profile not found.")
            return
        # Open default editor
        if sys.platform == "win32":
            os.startfile(prof)
        elif sys.platform == "darwin":
            subprocess.call(["open", prof])
        else:
            subprocess.call(["xdg-open", prof])


def handle_target(args):
    targets_dir = get_bundled_data_dir() / "data" / "targets"
    if args.target_cmd == "list":
        if targets_dir.exists():
            for f in targets_dir.glob("*.yaml"):
                print(f"- {f.stem}")
        else:
            print("No targets found.")
    elif args.target_cmd == "show":
        t = targets_dir / f"{args.name}.yaml"
        if t.exists():
            print(t.read_text(encoding="utf-8"))
        else:
            print(f"Target '{args.name}' not found.")


def handle_cache(args):
    if args.cache_cmd == "clear":
        from arb.core.cache import CacheManager
        print("🧹 Clearing local SQLite cache...")
        CacheManager().clear()


def main():
    parser = argparse.ArgumentParser(prog="arb", description="Auto Resume Builder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # arb init
    subparsers.add_parser("init", help="Initialize ARB profile and settings")

    # arb doctor
    subparsers.add_parser("doctor", help="Check system health and dependencies")

    # arb build
    build_parser = subparsers.add_parser("build", help="Build resume PDF")
    build_parser.add_argument("--target", type=str, help="Target loadout (e.g. backend)")
    build_parser.add_argument("--job", type=str, help="Path to job description txt")
    build_parser.add_argument("--pages", type=int, help="Target page count")
    build_parser.add_argument("--output", type=str, help="Output PDF path")
    build_parser.add_argument("--mock-ai", action="store_true", help="Use mock AI responses")
    
    # arb source
    source_parser = subparsers.add_parser("source", help="Manage data sources")
    source_sub = source_parser.add_subparsers(dest="source_cmd", required=True)
    
    add_src = source_sub.add_parser("add", help="Add a new source")
    add_src.add_argument("type", choices=["github"], help="Type of source")
    add_src.add_argument("identifier", help="Identifier (e.g. Spidey6978/TransitOS)")
    add_src.add_argument("--mock-ai", action="store_true")
    
    source_sub.add_parser("list", help="List active sources")
    source_sub.add_parser("sync", help="Sync sources")
    source_sub.add_parser("remove", help="Remove a source")

    # arb profile
    profile_parser = subparsers.add_parser("profile", help="Manage canonical profile")
    profile_sub = profile_parser.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("show", help="Print the canonical profile")
    profile_sub.add_parser("edit", help="Open canonical profile in default editor")
    profile_sub.add_parser("path", help="Print path to canonical profile")

    # arb target
    target_parser = subparsers.add_parser("target", help="Manage targets")
    target_sub = target_parser.add_subparsers(dest="target_cmd", required=True)
    target_sub.add_parser("list", help="List available targets")
    show_target = target_sub.add_parser("show", help="Show target details")
    show_target.add_argument("name", help="Target name")

    # arb cache
    cache_parser = subparsers.add_parser("cache", help="Manage cache")
    cache_sub = cache_parser.add_subparsers(dest="cache_cmd", required=True)
    cache_sub.add_parser("clear", help="Clear SQLite cache")
    
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="  [!] %(levelname)s - %(name)s - %(message)s")

    if args.command == "init":
        handle_init(args)
    elif args.command == "doctor":
        handle_doctor(args)
    elif args.command == "build":
        handle_build(args)
    elif args.command == "source":
        handle_source(args)
    elif args.command == "profile":
        handle_profile(args)
    elif args.command == "target":
        handle_target(args)
    elif args.command == "cache":
        handle_cache(args)

if __name__ == "__main__":
    main()
