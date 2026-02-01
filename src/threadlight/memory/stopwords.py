"""
Stop word filtering for semantic memory recall.

Prevents common words from flooding context with irrelevant matches.
"""

# Common English stop words that should not trigger memory recall
# This is a comprehensive list covering:
# - Articles, conjunctions, prepositions
# - Common pronouns
# - Auxiliary/modal verbs
# - Common adverbs
# - Question words (when used alone)
# - Common filler words

STOP_WORDS: frozenset[str] = frozenset({
    # Articles
    "a", "an", "the",

    # Conjunctions
    "and", "or", "but", "nor", "for", "yet", "so",
    "both", "either", "neither", "whether",

    # Prepositions
    "in", "on", "at", "to", "for", "with", "by", "from",
    "up", "down", "out", "off", "over", "under", "into",
    "through", "during", "before", "after", "above", "below",
    "between", "among", "about", "against", "within", "without",
    "along", "around", "behind", "beside", "beyond", "near",

    # Pronouns
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "this", "that", "these", "those",
    "who", "whom", "whose", "which", "what",
    "whoever", "whomever", "whatever", "whichever",
    "anyone", "someone", "everyone", "no one", "nobody",
    "anybody", "somebody", "everybody",
    "anything", "something", "everything", "nothing",
    "each", "every", "all", "some", "any", "none", "few", "many", "most",
    "other", "another", "such",

    # Auxiliary/modal verbs
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing", "done",
    "will", "would", "shall", "should",
    "can", "could", "may", "might", "must",
    "need", "ought",

    # Common verbs (when standalone)
    "get", "got", "getting", "gets",
    "go", "goes", "going", "went", "gone",
    "come", "comes", "coming", "came",
    "make", "makes", "making", "made",
    "take", "takes", "taking", "took", "taken",
    "see", "sees", "seeing", "saw", "seen",
    "know", "knows", "knowing", "knew", "known",
    "think", "thinks", "thinking", "thought",
    "say", "says", "saying", "said",
    "tell", "tells", "telling", "told",
    "let", "lets", "letting",
    "put", "puts", "putting",
    "give", "gives", "giving", "gave", "given",

    # Adverbs
    "not", "very", "really", "just", "only", "also", "too",
    "now", "then", "here", "there", "where", "when", "how", "why",
    "always", "never", "often", "sometimes", "usually",
    "already", "still", "yet", "ever", "even",
    "more", "most", "less", "least",
    "well", "much", "quite", "rather",
    "again", "back", "away", "together",

    # Question/relative words
    "what", "which", "who", "whom", "whose",
    "where", "when", "why", "how",

    # Determiners/quantifiers
    "no", "yes", "not",
    "one", "two", "first", "second", "last",
    "same", "different", "own",

    # Common filler/discourse words
    "like", "just", "well", "okay", "ok", "oh", "um", "uh",
    "please", "thanks", "thank", "sorry",
    "yes", "no", "yeah", "yep", "nope",
    "hi", "hello", "hey", "bye", "goodbye",

    # Contractions (common word parts)
    "don", "doesn", "didn", "won", "wouldn", "can", "couldn",
    "shouldn", "isn", "aren", "wasn", "weren", "hasn", "haven", "hadn",
    "ll", "ve", "re", "nt",  # Parts after apostrophe removal
})

# Minimum word length after stop word filtering
# Words shorter than this are likely not meaningful for recall
MIN_WORD_LENGTH = 3


def filter_stop_words(words: list[str], min_length: int = MIN_WORD_LENGTH) -> list[str]:
    """
    Filter out stop words and short words from a list.

    Args:
        words: List of words to filter
        min_length: Minimum word length to keep (default: 3)

    Returns:
        List of meaningful words for recall
    """
    return [
        w for w in words
        if len(w) >= min_length and w.lower() not in STOP_WORDS
    ]


def extract_meaningful_terms(text: str, min_length: int = MIN_WORD_LENGTH) -> list[str]:
    """
    Extract meaningful terms from text for memory recall.

    - Lowercases text
    - Removes punctuation
    - Filters stop words
    - Removes duplicates while preserving order

    Args:
        text: Input text to extract terms from
        min_length: Minimum word length to keep

    Returns:
        List of unique meaningful terms
    """
    import re

    # Remove punctuation and split into words
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    # Filter stop words and short words
    meaningful = filter_stop_words(words, min_length)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for word in meaningful:
        if word not in seen:
            seen.add(word)
            unique.append(word)

    return unique
