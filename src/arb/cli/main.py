import os
import sys
import argparse
import logging
import platform
import subprocess
from pathlib import Path
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
    from arb.adapters.document_adapter import DocumentAdapter
    from arb.core.document_segmenter import DocumentSegmenter
    from arb.core.evidence_extractor import EvidenceExtractor
    from arb.core.source_manager import SourceManager

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
    doc_adapter = DocumentAdapter()
    
    from arb.adapters.manual_adapter import ManualAdapter
    manual_adapter = ManualAdapter()
    
    from arb.adapters.linkedin_adapter import LinkedInAdapter
    linkedin_adapter = LinkedInAdapter()
    
    adapter_registry = AdapterRegistry()
    adapter_registry.register("github", github_adapter)
    adapter_registry.register("document", doc_adapter)
    adapter_registry.register("manual", manual_adapter)
    adapter_registry.register("linkedin", linkedin_adapter)

    extractor = FactExtractor(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    generator = ContentGenerator(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    
    canonical_path = get_user_data_dir() / "canonical_profile.yaml"
    if not canonical_path.exists():
        print(f"  [!] Canonical profile not found at {canonical_path}")
        print("      Run 'arb init' to set up your profile.")
        sys.exit(1)
        
    profile_manager = ProfileManager(str(canonical_path))
    
    templates_dir = get_bundled_data_dir() / "templates"
    
    # Auto-detect compiler
    import shutil
    from arb.core.compilers.engines import LuaLaTeXEngine, TectonicEngine
    if shutil.which("tectonic"):
        engine = TectonicEngine()
    elif shutil.which("lualatex"):
        engine = LuaLaTeXEngine()
    else:
        engine = TectonicEngine() # fallback to tectonic default
        
    compiler = ResumeCompiler(templates_dir=str(templates_dir), engine=engine)
    
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

    doc_segmenter = DocumentSegmenter(ai_gateway=ai_gateway, cache_manager=cache_mgr)
    evidence_extractor = EvidenceExtractor(ai_gateway=ai_gateway, cache_manager=cache_mgr, fact_extractor=extractor)
    source_manager = SourceManager(data_dir=get_user_data_dir())

    pipeline = BuildPipeline(
        profile_manager=profile_manager,
        adapter_registry=adapter_registry,
        extractor=extractor,
        generator=generator,
        compiler=compiler,
        target_engine=target_engine,
        domain_loader=domain_loader,
        document_segmenter=doc_segmenter,
        evidence_extractor=evidence_extractor,
        source_manager=source_manager
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
            print(f"Found an existing repository profile at:\n{legacy_path}\n")
            ans = input("Import it into ARB? [Y/n] ").strip().lower()
            if ans in ["y", "yes", ""]:
                try:
                    from arb.core.profile_manager import CanonicalProfile
                    import yaml
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    CanonicalProfile(**data)
                    import shutil
                    shutil.copy(legacy_path, canonical_path)
                    print("Migration complete.")
                except Exception as e:
                    print(f"Legacy profile could not be validated: {e}")
                    print("Nothing was changed.")
            else:
                print("Skipped migration.")
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
    
    checks = {
        "data_dir": False,
        "profile": False,
        "ai": False,
        "compiler": False
    }
    
    # Python
    print(f"✓ Python {platform.python_version()}")
    
    # Data Dir
    data_dir = get_user_data_dir()
    if data_dir.exists() and os.access(data_dir, os.W_OK):
        print(f"✓ User data directory ({data_dir})")
        checks["data_dir"] = True
    else:
        print(f"✗ User data directory is missing or not writable: {data_dir}")
        
    # Profile
    prof = data_dir / "canonical_profile.yaml"
    if prof.exists():
        try:
            from arb.core.profile_manager import CanonicalProfile
            import yaml
            with open(prof, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            CanonicalProfile(**data)
            print("✓ Canonical profile valid")
            checks["profile"] = True
        except Exception as e:
            print(f"✗ Canonical profile malformed: {e}")
    else:
        print("✗ Canonical profile missing (run 'arb init')")
        
    # Keys
    if os.getenv("GEMINI_API_KEY"):
        print("✓ GEMINI_API_KEY found")
        checks["ai"] = True
    else:
        print("✗ GEMINI_API_KEY not set")
        
    if os.getenv("GITHUB_TOKEN"):
        print("✓ GitHub token found")
    else:
        print("! GitHub token not set (public repos only, rate limits apply)")
        
    # Compiler
    import shutil
    if shutil.which("lualatex"):
        print("✓ LuaLaTeX compiler found")
        checks["compiler"] = True
    elif shutil.which("tectonic"):
        print("✓ Tectonic compiler found")
        checks["compiler"] = True
    else:
        print("✗ No LaTeX compiler (LuaLaTeX or Tectonic) found in PATH")
        
    print("-" * 30)
    ready = all(checks.values())
    print("Ready to build." if ready else "Not ready.")


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
        if args.type in ["github", "document", "manual", "linkedin"]:
            if args.type == "manual":
                entity_type = args.entity or input("Entity type to add (experience, project, education, award): ").strip()
                
                print(f"\n--- Adding Manual {entity_type.capitalize()} ---")
                data = {}
                if entity_type == "experience":
                    org = input("Organization/Company: ").strip()
                    title = input("Job Title: ").strip()
                    if org and title:
                        start_date = input("Start Date (e.g., 2020): ").strip()
                        end_date = input("End Date (e.g., 2022, Present): ").strip()
                        print("\nEnter facts/bullets for this experience (leave blank to finish):")
                        facts = []
                        while True:
                            fact = input(" - ").strip()
                            if not fact: break
                            facts.append(fact)
                        data = {"organization": org, "title": title, "start_date": start_date, "end_date": end_date, "facts": facts}
                elif entity_type == "project":
                    name = input("Project Name: ").strip()
                    if name:
                        link = input("Link (optional): ").strip()
                        tech = input("Tech Stack (comma separated): ").strip()
                        print("\nEnter facts/bullets for this project (leave blank to finish):")
                        facts = []
                        while True:
                            fact = input(" - ").strip()
                            if not fact: break
                            facts.append(fact)
                        data = {"name": name, "link": link, "tech_stack": [t.strip() for t in tech.split(",")] if tech else [], "facts": facts}
                elif entity_type == "education":
                    inst = input("Institution/School: ").strip()
                    degree = input("Degree (e.g., B.S. Computer Science): ").strip()
                    if inst and degree:
                        start_date = input("Start Date: ").strip()
                        end_date = input("End Date: ").strip()
                        data = {"institution": inst, "degree": degree, "start_date": start_date, "end_date": end_date}
                elif entity_type == "award":
                    title = input("Award Title: ").strip()
                    if title:
                        event = input("Event/Competition (optional): ").strip()
                        org = input("Organization (optional): ").strip()
                        year = input("Year (optional): ").strip()
                        print("\nEnter facts/bullets for this award (leave blank to finish):")
                        facts = []
                        while True:
                            fact = input(" - ").strip()
                            if not fact: break
                            facts.append(fact)
                        data = {"title": title, "event": event, "organization": org, "year": year, "facts": facts}

                if not data:
                    print("User cancelled or provided empty data.")
                    return
                
                import json
                args.identifier = json.dumps({"entity_type": entity_type, "data": data})
                
            pipeline, _, _ = init_services(args)
            if args.type != "manual":
                print(f"🔄 Syncing {args.type} source: {args.identifier}")
            result = pipeline.sync_source(source_type=args.type, identifier=args.identifier, mock_ai=args.mock_ai)
            if result.success:
                print(f"  [OK] {result.message}")
            else:
                print(f"  [!] {result.message}")
        else:
            print(f"Source type '{args.type}' not fully supported yet.")
    elif args.source_cmd == "list":
        from arb.core.source_manager import SourceManager
        import datetime
        
        manager = SourceManager(data_dir=get_user_data_dir())
        sources = manager.list_sources()
        if not sources:
            print("No sources registered.")
            return
            
        grouped = {}
        for s in sources:
            grouped.setdefault(s.type, []).append(s)
            
        for stype, s_list in grouped.items():
            print(f"\n{stype.capitalize()}")
            print("-" * 15)
            for s in s_list:
                print(s.display_name)
                try:
                    dt = datetime.datetime.fromisoformat(s.last_synced.replace('Z', '+00:00'))
                    date_str = dt.strftime("%d %b %Y %H:%M")
                except:
                    date_str = s.last_synced
                print(f"Last synced: {date_str} [{s.status.upper()}]\n")


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
    add_src.add_argument("type", choices=["github", "document", "manual", "linkedin"], help="Type of source")
    add_src.add_argument("identifier", nargs="?", help="Identifier (e.g. Spidey6978/TransitOS, path/to/resume.pdf, path/to/linkedin.zip)")
    add_src.add_argument("--entity", help="Entity type for manual entry (experience, project, education, award)")
    add_src.add_argument("--mock-ai", action="store_true")
    
    source_sub.add_parser("list", help="List all registered sources and sync status")

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
