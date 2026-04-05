import os
import google.generativeai as genai

# Cache to prevent pinging the API multiple times for the model list
_AVAILABLE_MODELS_CACHE = None

def get_available_models(api_key):
    global _AVAILABLE_MODELS_CACHE
    if _AVAILABLE_MODELS_CACHE is not None:
        return _AVAILABLE_MODELS_CACHE
        
    genai.configure(api_key=api_key)
    try:
        _AVAILABLE_MODELS_CACHE = [
            m.name.replace('models/', '')
            for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
    except Exception as e:
        print(f"  [!] Could not fetch model list: {e}")
        _AVAILABLE_MODELS_CACHE = []
        
    return _AVAILABLE_MODELS_CACHE

def generate_bullets_from_readme(repo_name, readme_content, is_umbrella):
    """
    Takes a raw README string and uses Gemini to generate ATS-friendly resume bullets.
    """
    if not readme_content or len(readme_content.strip()) < 50:
        return [
            "Architected core system components and maintained repository.",
            "Optimized application performance and resolved technical debt."
        ]
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  [!] GEMINI_API_KEY not found in .env. Falling back to default descriptions.")
        return ["Add GEMINI_API_KEY to your .env file to generate bullets!"]

    # Configure the Gemini API
    genai.configure(api_key=api_key)
    
    truncated_readme = readme_content[:40000]
    
    context_type = "a grouped full-stack project" if is_umbrella else "a technical repository"
    
    prompt = f"""
    You are an elite ATS resume writer and senior engineering recruiter. I have {context_type} named '{repo_name}'.
    Here is the content of the README.md:
    
    {truncated_readme}
    
    Your task: Generate exactly 2 professional, highly technical resume bullet points summarizing the architecture, logic, and impact of this project.
    Rules:
    - Analyze the entire README. Deeply extract the complex logic, math, physics, or architectural patterns used (ignore fluff and licenses).
    - Start each bullet with a strong, VARIED past-tense action verb (e.g., Architected, Designed, Orchestrated, Optimized, Spearheaded, Integrated). DO NOT repeat the same starting verb across bullets.
    - Quantify impact where possible and aggressively highlight the tech stack/frameworks.
    - Never invent compound architectural terms. Use precise standard terminology only.
    - DO NOT include markdown formatting like asterisks (*), bolding, or hyphens at the start.
    - STRICT LENGTH LIMIT: Keep each bullet punchy, around 15-25 words, so it fits exactly on a single line in a PDF.
    - Return ONLY the 2 bullet points, separated by a newline.
    """
    
    # Dynamically fetch what models your specific API key has access to
    available_models = get_available_models(api_key)
    
    # Define a hierarchy of models to try in order of preference
    preferred_order = [
        'gemini-2.5-flash', # Best quality
        'gemini-1.5-flash', # Great quality, high limits
        'gemini-1.5-pro',
        'gemini-pro',       # Legacy 1.0 Pro (Universally available fallback)
        'gemini-1.0-pro'
    ]
    
    # Filter to only try models that Google explicitly says your API key has access to
    models_to_try = [m for m in preferred_order if m in available_models]
    
    # If none of our preferred models are found, try whatever text model is available
    if not models_to_try and available_models:
        models_to_try.append(available_models[0])
        
    # Absolute fallback if list_models() completely failed
    if not models_to_try:
        models_to_try = ['gemini-pro']
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            bullets = response.text.strip().split('\n')
            
            # Clean up any rogue hyphens or bullet characters the LLM might hallucinate
            cleaned_bullets = [b.lstrip('- *•').strip() for b in bullets if b.strip()]
            return cleaned_bullets[:2]
            
        except Exception as e:
            # If a model fails (e.g., rate limit), log it and the loop continues to the next one
            print(f"  [!] {model_name} failed: {e}. Trying next model...")
            
    # If the loop finishes and ALL models have failed
    print("  [!] All Gemini models failed or are rate-limited. Using generic fallback bullets.")
    return [
        "Engineered core features and optimized system architecture.",
        "Resolved critical technical issues to ensure platform stability."
    ]