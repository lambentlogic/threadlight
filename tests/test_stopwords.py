"""
Tests for stop word filtering in semantic memory recall.
"""

import pytest
from threadlight.memory.stopwords import (
    STOP_WORDS,
    filter_stop_words,
    extract_meaningful_terms,
)


class TestStopWords:
    """Test the stop word list."""

    def test_common_articles_are_stop_words(self):
        """Articles should be in stop words."""
        assert "a" in STOP_WORDS
        assert "an" in STOP_WORDS
        assert "the" in STOP_WORDS

    def test_common_conjunctions_are_stop_words(self):
        """Conjunctions should be in stop words."""
        assert "and" in STOP_WORDS
        assert "or" in STOP_WORDS
        assert "but" in STOP_WORDS

    def test_common_pronouns_are_stop_words(self):
        """Pronouns should be in stop words."""
        assert "he" in STOP_WORDS
        assert "she" in STOP_WORDS
        assert "it" in STOP_WORDS
        assert "they" in STOP_WORDS
        assert "you" in STOP_WORDS
        assert "me" in STOP_WORDS

    def test_common_verbs_are_stop_words(self):
        """Common auxiliary verbs should be in stop words."""
        assert "is" in STOP_WORDS
        assert "was" in STOP_WORDS
        assert "are" in STOP_WORDS
        assert "have" in STOP_WORDS
        assert "has" in STOP_WORDS

    def test_question_words_are_stop_words(self):
        """Question words should be in stop words."""
        assert "what" in STOP_WORDS
        assert "where" in STOP_WORDS
        assert "when" in STOP_WORDS
        assert "how" in STOP_WORDS
        assert "why" in STOP_WORDS

    def test_common_adverbs_are_stop_words(self):
        """Common adverbs should be in stop words."""
        assert "here" in STOP_WORDS
        assert "there" in STOP_WORDS
        assert "just" in STOP_WORDS
        assert "very" in STOP_WORDS


class TestFilterStopWords:
    """Test the filter_stop_words function."""

    def test_filters_stop_words(self):
        """Should filter out stop words."""
        words = ["the", "cat", "and", "dog"]
        result = filter_stop_words(words)
        assert result == ["cat", "dog"]

    def test_filters_short_words(self):
        """Should filter out words shorter than min_length."""
        words = ["cat", "a", "dog", "it"]
        result = filter_stop_words(words, min_length=3)
        assert result == ["cat", "dog"]

    def test_case_insensitive(self):
        """Should handle mixed case."""
        words = ["The", "CAT", "AND", "Dog"]
        result = filter_stop_words(words)
        assert result == ["CAT", "Dog"]

    def test_preserves_meaningful_words(self):
        """Should preserve meaningful words."""
        words = ["memories", "friendship", "conversation", "about"]
        result = filter_stop_words(words)
        assert "memories" in result
        assert "friendship" in result
        assert "conversation" in result
        # "about" is a stop word
        assert "about" not in result

    def test_empty_input(self):
        """Should handle empty input."""
        result = filter_stop_words([])
        assert result == []

    def test_all_stop_words(self):
        """Should return empty list if all words are stop words."""
        words = ["the", "and", "or", "he", "she"]
        result = filter_stop_words(words)
        assert result == []


class TestExtractMeaningfulTerms:
    """Test the extract_meaningful_terms function."""

    def test_extracts_meaningful_terms(self):
        """Should extract meaningful terms from text."""
        text = "Can you tell me what memories you see here"
        result = extract_meaningful_terms(text)
        # Should NOT include: can, you, tell, me, what, see, here (all stop words)
        # Should include: memories
        assert "memories" in result
        assert "and" not in result
        assert "you" not in result
        assert "here" not in result
        assert "what" not in result

    def test_removes_punctuation(self):
        """Should remove punctuation."""
        text = "Hello, world! How's it going?"
        result = extract_meaningful_terms(text)
        # All these are stop words or too short
        # "hello" is a stop word, "world" should pass through
        assert "world" in result

    def test_deduplicates(self):
        """Should remove duplicate terms."""
        text = "cat cat dog cat dog dog"
        result = extract_meaningful_terms(text)
        assert result.count("cat") == 1
        assert result.count("dog") == 1

    def test_preserves_order(self):
        """Should preserve first occurrence order."""
        text = "cat dog bird cat dog"
        result = extract_meaningful_terms(text)
        assert result == ["cat", "dog", "bird"]

    def test_lowercase_output(self):
        """Should lowercase the output."""
        text = "The CAT and the DOG"
        result = extract_meaningful_terms(text)
        assert "cat" in result
        assert "dog" in result
        assert "CAT" not in result
        assert "DOG" not in result

    def test_problematic_query_from_logs(self):
        """Test the exact problematic query from the logs."""
        text = "can you tell me what memories you see here"
        result = extract_meaningful_terms(text)
        # This should NOT match "and", "or", "he", "she" etc.
        assert "and" not in result
        assert "or" not in result
        assert "he" not in result
        assert "she" not in result
        assert "memories" in result

    def test_another_problematic_pattern(self):
        """Test patterns that were causing noise."""
        # "About And:" was matching because "and" was extracted
        text = "Tell me about the weather and the news"
        result = extract_meaningful_terms(text)
        assert "and" not in result
        assert "weather" in result
        assert "news" in result

    def test_empty_input(self):
        """Should handle empty input."""
        result = extract_meaningful_terms("")
        assert result == []

    def test_only_stop_words(self):
        """Should return empty list if only stop words."""
        text = "the and or but if"
        result = extract_meaningful_terms(text)
        assert result == []
