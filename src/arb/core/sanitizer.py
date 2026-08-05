import re

def escape_latex(text: str) -> str:
    """
    Escapes special LaTeX characters in a string to prevent compilation errors.
    """
    if not isinstance(text, str):
        return text

    # Dictionary of characters that need to be escaped in LaTeX
    # Backslash must be processed first to avoid double-escaping later replacements
    latex_special_chars = {
        '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }

    # Create a regex pattern to match any of the special characters
    pattern = re.compile('|'.join(re.escape(key) for key in sorted(latex_special_chars.keys(), key=len, reverse=True)))
    
    # Replace the matched characters with their safe LaTeX equivalents
    return pattern.sub(lambda match: latex_special_chars[match.group(0)], text)

def sanitize_data(data, key_name=None):
    """
    Recursively traverses dictionaries and lists to escape LaTeX characters in all strings.
    """
    # Keys that should NEVER be sanitized because they act as raw URLs in \href{}
    do_not_escape_keys = {'link', 'github', 'linkedin', 'email'}
    
    if isinstance(data, dict):
        return {key: sanitize_data(value, key) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item, key_name) for item in data]
    elif isinstance(data, str):
        if key_name in do_not_escape_keys:
            return data
        return escape_latex(data)
    else:
        return data
