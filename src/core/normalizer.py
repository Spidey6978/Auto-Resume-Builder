from typing import Dict, List

def normalize_languages(languages: Dict[str, int], min_share: float = 0.03, max_languages: int = 4) -> List[str]:
    """
    Normalizes a dictionary of GitHub language byte counts into a clean list of tech tags.
    Uses proportional filtering to discard languages that make up a trivial percentage of the codebase.
    
    Args:
        languages: Dict mapping language name to byte count.
        min_share: Minimum proportion of total bytes required to be included.
        max_languages: Maximum number of languages to return.
        
    Returns:
        List of language names, sorted by byte count descending.
    """
    if not languages:
        return []
        
    total_bytes = sum(languages.values())
    if total_bytes == 0:
        return []
        
    meaningful = [
        (lang, count)
        for lang, count in languages.items()
        if (count / total_bytes) >= min_share
    ]
    
    # Sort by byte count descending
    meaningful.sort(key=lambda x: x[1], reverse=True)
    
    return [lang for lang, _ in meaningful[:max_languages]]
