import os
import google.generativeai as genai

def generate_bullets_from_readme(repo_name, readme_content):
    """
    Takes a raw README string and uses Gemini to generate ATS-friendly resume bullets.
    """
    if not readme_content or len(readme_content.strip()) < 50:
        return ["Developed and maintained the repository architecture."]
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  [!] GEMINI_API_KEY not found in .env. Falling back to default descriptions.")
        return ["Add GEMINI_API_KEY to your .env file to generate bullets!"]

    # Configure the Gemini API
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # We truncate the README to 3500 chars to avoid overwhelming the context window
    truncated_readme = readme_content[:3500]
    
    prompt = f"""
    You are an expert resume writer. I have a technical GitHub repository named '{repo_name}'.
    Here is the content of the README.md:
    
    {truncated_readme}
    
    Your task: Generate exactly 2 professional, ATS-friendly resume bullet points summarizing the technical impact and features of this project.
    Rules:
    - Start each bullet with a strong past-tense action verb (e.g., Architected, Engineered, Implemented).
    - Focus on the technologies used and the impact/purpose.
    - DO NOT include markdown formatting like asterisks (*), bolding, or hyphens at the start.
    - Return ONLY the bullet points, separated by a newline.
    """
    
    try:
        response = model.generate_content(prompt)
        bullets = response.text.strip().split('\n')
        # Clean up any rogue hyphens or bullet characters the LLM might hallucinate
        cleaned_bullets = [b.lstrip('- *•').strip() for b in bullets if b.strip()]
        return cleaned_bullets[:2]
    except Exception as e:
        print(f"  [!] Error calling Gemini API: {e}")
        return ["Built core application features and resolved technical issues."]