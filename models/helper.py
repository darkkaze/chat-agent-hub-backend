import random
import string
from typing import Callable


def id_generator(prefix: str, n: int) -> Callable[[], str]:
    """
    Generates a callable that returns unique IDs with format {prefix}_{n_chars_random}.
    
    Random characters exclude visually confusing characters:
    - Excludes: 0, O, 1, l, I
    - Only includes: 23456789abcdefghjkmnpqrstuvwxyz
    
    Args:
        prefix: ID prefix (e.g. 'user', 'agent')
        n: Number of random characters
        
    Returns:
        Function that generates IDs with format {prefix}_{random_chars}
    """
    safe_chars = '23456789abcdefghjkmnpqrstuvwxyz'
    
    def generate_id() -> str:
        random_part = ''.join(random.choices(safe_chars, k=n))
        return f"{prefix}_{random_part}"
    
    return generate_id