"""
Text Preprocessing Utilities

Comprehensive text preprocessing pipeline for NLP tasks including
cleaning, normalization, tokenization, and feature extraction.
"""

import re
import string
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
import unicodedata
from dataclasses import dataclass
import numpy as np

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.stem import WordNetLemmatizer, PorterStemmer
    from nltk.chunk import ne_chunk
    from nltk.tag import pos_tag
    NLTK_AVAILABLE = True
except ImportError:
    nltk = None
    word_tokenize = None
    sent_tokenize = None
    WordNetLemmatizer = None
    PorterStemmer = None
    stopwords = None
    NLTK_AVAILABLE = False

try:
    import spacy
except ImportError:
    spacy = None

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

try:
    import ftfy
except ImportError:
    ftfy = None

try:
    from unidecode import unidecode
except ImportError:
    unidecode = None

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Configuration for text preprocessing."""
    lowercase: bool = True
    remove_punctuation: bool = False
    remove_numbers: bool = False
    remove_stopwords: bool = False
    lemmatize: bool = True
    stem: bool = False
    remove_extra_whitespace: bool = True
    fix_encoding: bool = True
    normalize_unicode: bool = True
    remove_urls: bool = True
    remove_emails: bool = True
    remove_html: bool = True
    expand_contractions: bool = True
    min_word_length: int = 1
    max_word_length: int = 50
    language: str = "english"


@dataclass
class PreprocessingResult:
    """Result of text preprocessing."""
    original_text: str
    processed_text: str
    tokens: List[str]
    sentences: List[str]
    statistics: Dict[str, Any]
    metadata: Dict[str, Any]


class TextPreprocessor:
    """Comprehensive text preprocessing pipeline."""
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
        self.lemmatizer = None
        self.stemmer = None
        self.spacy_model = None
        self.stop_words = set()
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize preprocessing components."""
        try:
            # Initialize NLTK components
            if self.config.lemmatize and NLTK_AVAILABLE and WordNetLemmatizer:
                self.lemmatizer = WordNetLemmatizer()
            
            if self.config.stem and NLTK_AVAILABLE and PorterStemmer:
                self.stemmer = PorterStemmer()
            
            # Load stopwords
            if self.config.remove_stopwords and NLTK_AVAILABLE and stopwords:
                try:
                    self.stop_words = set(stopwords.words(self.config.language))
                except:
                    self.stop_words = set(stopwords.words('english'))
            
            # Try to load spaCy model
            if spacy:
                try:
                    self.spacy_model = spacy.load("en_core_web_sm")
                except OSError:
                    logger.warning("spaCy model not found, some features will be limited")
            
            logger.info("Text preprocessor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize preprocessor components: {e}")
    
    def preprocess(self, text: str, custom_config: Optional[PreprocessingConfig] = None) -> PreprocessingResult:
        """
        Preprocess text according to configuration.
        
        Args:
            text: Input text to preprocess
            custom_config: Optional custom configuration for this operation
            
        Returns:
            PreprocessingResult with processed text and metadata
        """
        config = custom_config or self.config
        original_text = text
        
        # Track statistics
        stats: Dict[str, Any] = {
            "original_length": len(text),
            "original_words": len(text.split()),
            "original_sentences": len(sent_tokenize(text)) if nltk else len(text.split('.')),
        }
        
        try:
            # Step 1: Fix encoding issues
            if config.fix_encoding:
                text = self._fix_encoding(text)
            
            # Step 2: Normalize Unicode
            if config.normalize_unicode:
                text = self._normalize_unicode(text)
            
            # Step 3: Remove HTML tags
            if config.remove_html:
                text = self._remove_html(text)
            
            # Step 4: Remove URLs and emails
            if config.remove_urls:
                text = self._remove_urls(text)
            
            if config.remove_emails:
                text = self._remove_emails(text)
            
            # Step 5: Expand contractions
            if config.expand_contractions:
                text = self._expand_contractions(text)
            
            # Step 6: Lowercase
            if config.lowercase:
                text = text.lower()
            
            # Step 7: Remove extra whitespace
            if config.remove_extra_whitespace:
                text = self._remove_extra_whitespace(text)
            
            # Step 8: Remove punctuation
            if config.remove_punctuation:
                text = self._remove_punctuation(text)
            
            # Step 9: Remove numbers
            if config.remove_numbers:
                text = self._remove_numbers(text)
            
            # Step 10: Tokenize
            tokens = self._tokenize(text)
            
            # Step 11: Filter tokens by length
            tokens = self._filter_by_length(tokens, config.min_word_length, config.max_word_length)
            
            # Step 12: Remove stopwords
            if config.remove_stopwords:
                tokens = self._remove_stopwords(tokens)
            
            # Step 13: Lemmatize or stem
            if config.lemmatize and self.lemmatizer:
                tokens = self._lemmatize_tokens(tokens)
            elif config.stem and self.stemmer:
                tokens = self._stem_tokens(tokens)
            
            # Reconstruct processed text
            processed_text = ' '.join(tokens)
            
            # Get sentences from processed text
            sentences = sent_tokenize(processed_text) if nltk else processed_text.split('.')
            
            # Update statistics
            stats.update({
                "processed_length": len(processed_text),
                "processed_words": len(tokens),
                "processed_sentences": len(sentences),
                "reduction_ratio": 1 - (len(processed_text) / len(original_text)) if len(original_text) > 0 else 0
            })
            
            return PreprocessingResult(
                original_text=original_text,
                processed_text=processed_text,
                tokens=tokens,
                sentences=sentences,
                statistics=stats,
                metadata={
                    "config": config.__dict__,
                    "preprocessing_steps": self._get_applied_steps(config)
                }
            )
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            # Return minimally processed result
            return PreprocessingResult(
                original_text=original_text,
                processed_text=text,
                tokens=text.split(),
                sentences=[text],
                statistics=stats,
                metadata={"error": str(e)}
            )
    
    def _fix_encoding(self, text: str) -> str:
        """Fix encoding issues in text."""
        try:
            if ftfy:
                return ftfy.fix_text(text)
            else:
                return text
        except:
            return text
    
    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters."""
        try:
            # Normalize to NFD (decomposed) form
            text = unicodedata.normalize('NFD', text)
            # Convert to ASCII if possible
            if unidecode:
                text = unidecode(text)
            return text
        except:
            return text
    
    def _remove_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        try:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(text, "html.parser")
                return soup.get_text()
            except ImportError:
                # Fallback regex
                clean = re.compile('<.*?>')
                return re.sub(clean, '', text)
        except:
            # Fallback regex
            clean = re.compile('<.*?>')
            return re.sub(clean, '', text)
    
    def _remove_urls(self, text: str) -> str:
        """Remove URLs from text."""
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        return url_pattern.sub('', text)
    
    def _remove_emails(self, text: str) -> str:
        """Remove email addresses from text."""
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        return email_pattern.sub('', text)
    
    def _expand_contractions(self, text: str) -> str:
        """Expand English contractions."""
        contractions_dict = {
            "ain't": "am not",
            "aren't": "are not",
            "can't": "cannot",
            "couldn't": "could not",
            "didn't": "did not",
            "doesn't": "does not",
            "don't": "do not",
            "hadn't": "had not",
            "hasn't": "has not",
            "haven't": "have not",
            "he'd": "he would",
            "he'll": "he will",
            "he's": "he is",
            "i'd": "i would",
            "i'll": "i will",
            "i'm": "i am",
            "i've": "i have",
            "isn't": "is not",
            "it'd": "it would",
            "it'll": "it will",
            "it's": "it is",
            "let's": "let us",
            "shouldn't": "should not",
            "that's": "that is",
            "there's": "there is",
            "they'd": "they would",
            "they'll": "they will",
            "they're": "they are",
            "they've": "they have",
            "we'd": "we would",
            "we're": "we are",
            "we've": "we have",
            "weren't": "were not",
            "what's": "what is",
            "where's": "where is",
            "who's": "who is",
            "won't": "will not",
            "wouldn't": "would not",
            "you'd": "you would",
            "you'll": "you will",
            "you're": "you are",
            "you've": "you have"
        }
        
        for contraction, expansion in contractions_dict.items():
            text = re.sub(re.escape(contraction), expansion, text, flags=re.IGNORECASE)
        
        return text
    
    def _remove_extra_whitespace(self, text: str) -> str:
        """Remove extra whitespace and normalize spacing."""
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text
    
    def _remove_punctuation(self, text: str) -> str:
        """Remove punctuation from text."""
        translator = str.maketrans('', '', string.punctuation)
        return text.translate(translator)
    
    def _remove_numbers(self, text: str) -> str:
        """Remove numbers from text."""
        return re.sub(r'\d+', '', text)
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        try:
            if nltk and word_tokenize:
                return word_tokenize(text)
            else:
                # Fallback to simple split
                return text.split()
        except:
            # Fallback to simple split
            return text.split()
    
    def _filter_by_length(self, tokens: List[str], min_length: int, max_length: int) -> List[str]:
        """Filter tokens by length."""
        return [
            token for token in tokens 
            if min_length <= len(token) <= max_length
        ]
    
    def _remove_stopwords(self, tokens: List[str]) -> List[str]:
        """Remove stopwords from tokens."""
        return [token for token in tokens if token.lower() not in self.stop_words]
    
    def _lemmatize_tokens(self, tokens: List[str]) -> List[str]:
        """Lemmatize tokens."""
        try:
            if self.lemmatizer:
                return [self.lemmatizer.lemmatize(token) for token in tokens]
            else:
                return tokens
        except:
            return tokens
    
    def _stem_tokens(self, tokens: List[str]) -> List[str]:
        """Stem tokens."""
        try:
            if self.stemmer:
                return [self.stemmer.stem(token) for token in tokens]
            else:
                return tokens
        except:
            return tokens
    
    def _get_applied_steps(self, config: PreprocessingConfig) -> List[str]:
        """Get list of applied preprocessing steps."""
        steps = []
        
        if config.fix_encoding:
            steps.append("fix_encoding")
        if config.normalize_unicode:
            steps.append("normalize_unicode")
        if config.remove_html:
            steps.append("remove_html")
        if config.remove_urls:
            steps.append("remove_urls")
        if config.remove_emails:
            steps.append("remove_emails")
        if config.expand_contractions:
            steps.append("expand_contractions")
        if config.lowercase:
            steps.append("lowercase")
        if config.remove_extra_whitespace:
            steps.append("remove_extra_whitespace")
        if config.remove_punctuation:
            steps.append("remove_punctuation")
        if config.remove_numbers:
            steps.append("remove_numbers")
        if config.remove_stopwords:
            steps.append("remove_stopwords")
        if config.lemmatize:
            steps.append("lemmatize")
        if config.stem:
            steps.append("stem")
        
        return steps
    
    def extract_features(self, text: str) -> Dict[str, Any]:
        """Extract various text features for analysis."""
        try:
            # Basic statistics
            word_count = len(text.split())
            char_count = len(text)
            sentence_count = len(sent_tokenize(text))
            
            # Advanced features using TextBlob
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # Language features
            avg_word_length = np.mean([len(word) for word in text.split()]) if word_count > 0 else 0
            avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
            
            # Character-level features
            uppercase_ratio = sum(1 for c in text if c.isupper()) / char_count if char_count > 0 else 0
            digit_ratio = sum(1 for c in text if c.isdigit()) / char_count if char_count > 0 else 0
            punctuation_ratio = sum(1 for c in text if c in string.punctuation) / char_count if char_count > 0 else 0
            
            # Vocabulary features
            unique_words = len(set(text.lower().split()))
            vocabulary_richness = unique_words / word_count if word_count > 0 else 0
            
            return {
                "word_count": word_count,
                "char_count": char_count,
                "sentence_count": sentence_count,
                "avg_word_length": avg_word_length,
                "avg_sentence_length": avg_sentence_length,
                "uppercase_ratio": uppercase_ratio,
                "digit_ratio": digit_ratio,
                "punctuation_ratio": punctuation_ratio,
                "unique_words": unique_words,
                "vocabulary_richness": vocabulary_richness,
                "sentiment_polarity": polarity,
                "sentiment_subjectivity": subjectivity
            }
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return {"error": str(e)}
    
    def clean_for_training(self, texts: List[str], labels: List[Any]) -> Tuple[List[str], List[Any]]:
        """Clean text data for training purposes."""
        cleaned_texts = []
        cleaned_labels = []
        
        for text, label in zip(texts, labels):
            try:
                # Apply minimal cleaning for training
                config = PreprocessingConfig(
                    lowercase=True,
                    remove_extra_whitespace=True,
                    fix_encoding=True,
                    remove_html=True,
                    remove_urls=True,
                    remove_emails=True
                )
                
                result = self.preprocess(text, config)
                
                # Only keep if processed text is meaningful
                if len(result.processed_text.strip()) > 10:
                    cleaned_texts.append(result.processed_text)
                    cleaned_labels.append(label)
                    
            except Exception as e:
                logger.warning(f"Failed to clean text for training: {e}")
                continue
        
        return cleaned_texts, cleaned_labels
    
    def prepare_for_vectorization(self, texts: List[str]) -> List[str]:
        """Prepare texts for vectorization (TF-IDF, embeddings, etc.)."""
        processed_texts = []
        
        config = PreprocessingConfig(
            lowercase=True,
            remove_punctuation=False,  # Keep some punctuation for context
            remove_numbers=False,
            remove_stopwords=True,
            lemmatize=True,
            remove_extra_whitespace=True,
            fix_encoding=True,
            normalize_unicode=True
        )
        
        for text in texts:
            try:
                result = self.preprocess(text, config)
                processed_texts.append(result.processed_text)
            except Exception as e:
                logger.warning(f"Failed to prepare text for vectorization: {e}")
                processed_texts.append(text)  # Use original as fallback
        
        return processed_texts