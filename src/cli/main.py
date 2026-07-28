import os
import sys
import yaml
import time
import argparse
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

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Auto Resume Builder — CLI")
    parser.add_argument(
        "--mock-ai",
        action="store_true",
        help="Skip Gemini API calls and use simulated placeholder bullets.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear local SQLite cache before building.",
    )
    args = parser.parse_args()

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

    # Locate static profile data
    data_path = os.path.join(base_dir, "data", "static_profile.yaml")
    if not os.path.exists(data_path):
        print("  [!] Real static_profile.yaml not found. Falling back to dummy data.")
        data_path = os.path.join(base_dir, "data", "dummy_static_profile.yaml")

    with open(data_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    github_user = raw_data.get("github_username")
    github_token = os.getenv("GITHUB_TOKEN")

    github_adapter = GitHubAdapter(token=github_token, cache_manager=cache_mgr)
    ai_gateway = AIGateway(cache_manager=cache_mgr)

    all_projects = []

    # 1. Process Grouped / Umbrella Repos
    for group in raw_data.get("grouped_repos", []):
        print(f"Processing Umbrella Project: '{group['name']}'...")
        combined_readme = ""
        combined_tech = set()
        first_repo_name = group["repos"][0] if group["repos"] else group["name"]

        for repo_name in group["repos"]:
            data = github_adapter.get_repo_data(github_user, repo_name)
            if data:
                combined_readme += f"\n--- {repo_name} ---\n{data.get('readme_content', '')}"
                tech = data.get("tech_stack", "")
                if tech and tech != "Various":
                    combined_tech.update([t.strip() for t in tech.split(",")])

        bullets = ai_gateway.generate_bullets_from_readme(
            group["name"], combined_readme, is_umbrella=True, mock_ai=args.mock_ai
        )

        all_projects.append(
            {
                "name": group["name"],
                "tech_stack": ", ".join(list(combined_tech)[:5]),
                "link": f"https://github.com/{github_user}/{first_repo_name}",
                "bullets": bullets,
            }
        )

    # 2. Process Individual Showcase Repos
    showcase_names = raw_data.get("showcase_repos", [])
    if showcase_names:
        print(f"Processing Showcase Repositories ({len(showcase_names)})...")
        for repo_name in showcase_names:
            r = github_adapter.get_repo_data(github_user, repo_name)
            if r:
                content = r["readme_content"] if len(r.get("readme_content", "")) > 50 else r.get("description", "")
                bullets = ai_gateway.generate_bullets_from_readme(
                    r["name"], content, is_umbrella=False, mock_ai=args.mock_ai
                )
                all_projects.append(
                    {
                        "name": r["name"],
                        "tech_stack": r["tech_stack"],
                        "link": r["link"],
                        "bullets": bullets,
                    }
                )

    # 3. Handle Manual / Static Projects
    manual_projects = raw_data.get("projects", [])
    all_projects.extend(manual_projects)

    # 4. Prepare Final Data Payload
    final_data = raw_data.copy()
    final_data["projects"] = all_projects

    # 5. Render and Compile PDF
    templates_dir = os.path.join(base_dir, "templates")
    compiler = ResumeCompiler(templates_dir=templates_dir)

    rendered_tex = compiler.render("resume_template.tex", final_data)

    build_dir = os.path.join(base_dir, "build")
    os.makedirs(build_dir, exist_ok=True)
    tex_output_path = os.path.join(build_dir, "resume.tex")

    with open(tex_output_path, "w", encoding="utf-8") as f:
        f.write(rendered_tex)

    print(f"  LaTeX file generated at: {tex_output_path}")
    compiler.compile_pdf(tex_output_path)

    # Display Cache Stats
    stats = cache_mgr.stats()
    print(f"📊 Cache Stats: {stats}")
    print("=========================================")


if __name__ == "__main__":
    main()
