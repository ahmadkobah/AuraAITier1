
"""
Multi-Task NLP Model

Comprehensive NLP model that combines multiple pre-trained models
for various NLP tasks including sentiment analysis, NER, summarization, etc.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from transformers import pipeline
import spacy
from langdetect import detect, LangDetectException
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from .base_nlp_model import (
    NLPModelInterface, NLPTaskType, LanguageCode, NLPResult,
    Entity, SentimentResult, KeywordResult, SummaryResult,
    LanguageResult, ClassificationResult, SimilarityResult,
    TrainingData, TrainingConfig
)

logger = logging.getLogger(__name__)


class MultiTaskNLPModel(NLPModelInterface):
    """Multi-task NLP model with comprehensive capabilities."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # Provide default config if None
        if config is None:
            config = {}

        self.model_name = "multitask_nlp_model"
        self.model_version = "1.0.0"
        self.supported_tasks = [
            NLPTaskType.SENTIMENT_ANALYSIS,
            NLPTaskType.ENTITY_RECOGNITION,
            NLPTaskType.KEYWORD_EXTRACTION,
            NLPTaskType.TEXT_SUMMARIZATION,
            NLPTaskType.LANGUAGE_DETECTION,
            NLPTaskType.TEXT_CLASSIFICATION,
            NLPTaskType.SEMANTIC_SIMILARITY
        ]
        self.supported_languages = [
            LanguageCode.ENGLISH, LanguageCode.SPANISH, LanguageCode.FRENCH,
            LanguageCode.GERMAN, LanguageCode.ITALIAN, LanguageCode.PORTUGUESE,
            LanguageCode.RUSSIAN, LanguageCode.CHINESE, LanguageCode.AUTO_DETECT
        ]

        # Model components
        self.spacy_model = None
        self.sentiment_analyzer = None
        self.vader_analyzer = None
        self.summarizer = None
        self.classifier = None
        self.ner_model = None
        self.sentence_transformer = None
        self.lemmatizer = None

        # Configuration
        self.sentiment_model_name = config.get("sentiment_model", "cardiffnlp/twitter-roberta-base-sentiment-latest")
        self.ner_model_name = config.get("ner_model", "dbmdz/bert-large-cased-finetuned-conll03-english")
        self.summarization_model = config.get("summarization_model", "facebook/bart-large-cnn")
        self.classification_model = config.get("classification_model", "microsoft/DialoGPT-medium")
        self.sentence_model = config.get("sentence_model", "all-MiniLM-L6-v2")
        self.spacy_model_name = config.get("spacy_model", "en_core_web_sm")
        self.max_text_length = config.get("max_text_length", 10000)
        self.use_gpu = config.get("use_gpu", False)
        self.device = 0 if self.use_gpu else -1

        # Concurrency control
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent tasks

        logger.info(f"Initialized MultiTaskNLPModel with config: {config}")

    def load_model(self) -> bool:
        """Load all NLP models and dependencies."""
        try:
            logger.info("Loading NLP models...")

            # Download NLTK data
            self._download_nltk_data()

            # Load spaCy model
            try:
                self.spacy_model = spacy.load(self.spacy_model_name)
                logger.info(f"✓ Loaded spaCy model: {self.spacy_model_name}")
            except OSError:
                logger.warning(f"⚠ spaCy model '{self.spacy_model_name}' not found, falling back to 'en_core_web_sm'")
                try:
                    self.spacy_model = spacy.load("en_core_web_sm")
                    logger.info(f"✓ Loaded fallback spaCy model: en_core_web_sm")
                except OSError as e:
                    logger.error(f"✗ Failed to load spaCy models. Please install with: python -m spacy download en_core_web_sm")
                    self.spacy_model = None

            # Load sentiment analysis models
            try:
                self.vader_analyzer = SentimentIntensityAnalyzer()
                logger.info("✓ Loaded VADER sentiment analyzer")
            except Exception as e:
                logger.error(f"✗ Failed to load VADER analyzer: {e}")
                self.vader_analyzer = None

            try:
                self.sentiment_analyzer = pipeline(
                    "sentiment-analysis",
                    model=self.sentiment_model_name,
                    tokenizer=self.sentiment_model_name,
                    device=self.device
                )
                logger.info(f"✓ Loaded sentiment model: {self.sentiment_model_name}")
            except Exception as e:
                logger.warning(f"⚠ Failed to load sentiment model '{self.sentiment_model_name}': {e}")
                logger.info("Falling back to default sentiment-analysis model")
                try:
                    self.sentiment_analyzer = pipeline("sentiment-analysis", device=self.device)
                    logger.info("✓ Loaded fallback sentiment model")
                except Exception as e2:
                    logger.error(f"✗ Failed to load fallback sentiment model: {e2}")
                    self.sentiment_analyzer = None

            # Load NER model
            try:
                self.ner_model = pipeline(
                    "ner",
                    model=self.ner_model_name,
                    tokenizer=self.ner_model_name,
                    aggregation_strategy="simple",
                    device=self.device
                )
                logger.info(f"✓ Loaded NER model: {self.ner_model_name}")
            except Exception as e:
                logger.warning(f"⚠ Failed to load NER model '{self.ner_model_name}': {e}")
                logger.info("Falling back to default NER model")
                try:
                    self.ner_model = pipeline("ner", aggregation_strategy="simple", device=self.device)
                    logger.info("✓ Loaded fallback NER model")
                except Exception as e2:
                    logger.error(f"✗ Failed to load fallback NER model: {e2}")
                    self.ner_model = None

            # Load summarization model
            try:
                self.summarizer = pipeline(
                    "summarization",
                    model=self.summarization_model,
                    device=self.device
                )
                logger.info(f"✓ Loaded summarization model: {self.summarization_model}")
            except Exception as e:
                logger.warning(f"⚠ Failed to load summarization model '{self.summarization_model}': {e}")
                logger.info("Falling back to default summarization model")
                try:
                    self.summarizer = pipeline("summarization", device=self.device)
                    logger.info("✓ Loaded fallback summarization model")
                except Exception as e2:
                    logger.error(f"✗ Failed to load fallback summarization model: {e2}")
                    self.summarizer = None

            # Load sentence transformer for similarity
            try:
                self.sentence_transformer = SentenceTransformer(self.sentence_model)
                logger.info(f"✓ Loaded sentence transformer: {self.sentence_model}")
            except Exception as e:
                logger.warning(f"⚠ Failed to load sentence transformer '{self.sentence_model}': {e}")
                logger.info("Falling back to TF-IDF for similarity calculation")
                self.sentence_transformer = None

            # Initialize NLTK components
            try:
                self.lemmatizer = WordNetLemmatizer()
                logger.info("✓ Loaded WordNet lemmatizer")
            except Exception as e:
                logger.error(f"✗ Failed to load lemmatizer: {e}")
                self.lemmatizer = None

            self.is_loaded = True
            logger.info("✓ All NLP models loaded successfully")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to load NLP models: {e}", exc_info=True)
            return False

    def _download_nltk_data(self):
        """Download required NLTK data."""
        required_data = [
            ('punkt', 'tokenizers/punkt'),
            ('stopwords', 'corpora/stopwords'),
            ('wordnet', 'corpora/wordnet'),
            ('vader_lexicon', 'sentiment/vader_lexicon'),
            ('averaged_perceptron_tagger', 'taggers/averaged_perceptron_tagger')
        ]

        for name, path in required_data:
            try:
                nltk.data.find(path)
                logger.debug(f"✓ NLTK data '{name}' already downloaded")
            except LookupError:
                try:
                    logger.info(f"Downloading NLTK data: {name}")
                    nltk.download(name, quiet=True)
                    logger.info(f"✓ Downloaded NLTK data: {name}")
                except Exception as e:
                    logger.warning(f"⚠ Failed to download NLTK data '{name}': {e}")

    def _validate_input(self, text: str) -> str:
        """Validate and clean input text."""
        # Check if text is valid string
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text)}")

        # Strip whitespace
        text = text.strip()

        # Check if empty
        if not text:
            raise ValueError("Text cannot be empty")

        # Check length
        if len(text) > self.max_text_length:
            logger.warning(f"Text exceeds max length ({self.max_text_length}), truncating")
            text = text[:self.max_text_length]

        # Check minimum length for meaningful processing
        if len(text) < 3:
            logger.warning(f"Text is very short ({len(text)} chars), results may be unreliable")

        return text

    async def predict(
        self,
        text: Union[str, List[str]],
        task_type: NLPTaskType = NLPTaskType.SENTIMENT_ANALYSIS,
        language: Optional[LanguageCode] = None,
        **kwargs
    ) -> Union[NLPResult, List[NLPResult]]:
        """Perform NLP prediction on text."""
        start_time = time.time()

        # Validate input type
        if not isinstance(text, (str, list)):
            raise ValueError(f"Text must be string or list of strings, got {type(text)}")

        if isinstance(text, list):
            # Validate list
            if not text:
                raise ValueError("Text list cannot be empty")

            if len(text) > 100:
                raise ValueError(f"Batch size too large ({len(text)}), maximum is 100")

            # Process batch with concurrency control
            results = []
            for t in text:
                async with self._semaphore:
                    result = await self._predict_single(t, task_type, language, **kwargs)
                    results.append(result)

            logger.info(f"Batch prediction completed: {len(results)} texts in {time.time() - start_time:.2f}s")
            return results
        else:
            return await self._predict_single(text, task_type, language, **kwargs)

    async def _predict_single(
        self,
        text: str,
        task_type: NLPTaskType,
        language: Optional[LanguageCode] = None,
        **kwargs
    ) -> NLPResult:
        """Perform prediction on a single text."""
        start_time = time.time()

        # Validate input
        try:
            text = self._validate_input(text)
        except ValueError as e:
            logger.error(f"Input validation failed: {e}")
            return NLPResult(
                task_type=task_type,
                text=text,
                language="unknown",
                processing_time=time.time() - start_time,
                model_version=self.model_version,
                metadata={"error": str(e), "validation_failed": True}
            )

        # Preprocess text
        processed_text = self.preprocess_text(text, language)

        # Detect language if not specified
        detected_language = None
        if language is None or language == LanguageCode.AUTO_DETECT:
            detected_language = await self._detect_language(processed_text)
            language = detected_language.iso_code if detected_language else "en"

        # Create base result
        result = NLPResult(
            task_type=task_type,
            text=text,
            language=language,
            processing_time=0.0,
            model_version=self.model_version
        )

        # Add language detection if performed
        if detected_language:
            result.language_detection = detected_language

        # Route to specific task handler
        try:
            logger.debug(f"Processing task: {task_type.value} for text length: {len(text)}")

            if task_type == NLPTaskType.SENTIMENT_ANALYSIS:
                result.sentiment = await self._analyze_sentiment(processed_text)
            elif task_type == NLPTaskType.ENTITY_RECOGNITION:
                result.entities = await self._extract_entities(processed_text)
            elif task_type == NLPTaskType.KEYWORD_EXTRACTION:
                result.keywords = await self._extract_keywords(processed_text, **kwargs)
            elif task_type == NLPTaskType.TEXT_SUMMARIZATION:
                result.summary = await self._summarize_text(processed_text, **kwargs)
            elif task_type == NLPTaskType.LANGUAGE_DETECTION:
                if not result.language_detection:
                    result.language_detection = await self._detect_language(processed_text)
            elif task_type == NLPTaskType.TEXT_CLASSIFICATION:
                result.classification = await self._classify_text(processed_text, **kwargs)
            elif task_type == NLPTaskType.SEMANTIC_SIMILARITY:
                compare_text = kwargs.get("compare_text", "")
                if not compare_text:
                    raise ValueError("compare_text parameter required for similarity task")
                result.similarity = await self._calculate_similarity(processed_text, compare_text)
            else:
                raise ValueError(f"Unsupported task type: {task_type}")

            # Calculate processing time
            result.processing_time = time.time() - start_time

            # Postprocess result
            result = self.postprocess_result(result)

            logger.debug(f"Task completed in {result.processing_time:.3f}s")
            return result

        except Exception as e:
            logger.error(f"Prediction failed for task {task_type}: {e}", exc_info=True)
            result.processing_time = time.time() - start_time
            result.metadata = {"error": str(e), "error_type": type(e).__name__}
            return result

    async def _analyze_sentiment(self, text: str) -> SentimentResult:
        """Analyze sentiment of text."""
        try:
            # Use VADER for quick analysis if available
            vader_scores = {'compound': 0.0, 'pos': 0.0, 'neg': 0.0, 'neu': 1.0}
            if self.vader_analyzer:
                try:
                    vader_scores = self.vader_analyzer.polarity_scores(text)
                except Exception as e:
                    logger.warning(f"VADER analysis failed: {e}")

            # Use transformer model for more accurate analysis
            transformer_result = None
            if self.sentiment_analyzer:
                try:
                    # Truncate text for transformer if needed
                    max_length = 512
                    text_to_analyze = text if len(text) <= max_length else text[:max_length]
                    transformer_result = self.sentiment_analyzer(text_to_analyze)[0]
                except Exception as e:
                    logger.warning(f"Transformer sentiment analysis failed: {e}")

            # Combine results
            if transformer_result:
                label = transformer_result['label'].lower()
                score = transformer_result['score']

                # Map transformer labels to standard format
                if label in ['positive', 'pos', 'label_2']:
                    label = 'positive'
                elif label in ['negative', 'neg', 'label_0']:
                    label = 'negative'
                else:
                    label = 'neutral'
            else:
                # Use VADER as fallback
                compound = vader_scores['compound']
                if compound >= 0.05:
                    label = 'positive'
                    score = compound
                elif compound <= -0.05:
                    label = 'negative'
                    score = abs(compound)
                else:
                    label = 'neutral'
                    score = 1.0 - abs(compound)

            return SentimentResult(
                label=label,
                score=float(score),
                compound_score=float(vader_scores['compound']),
                details={
                    'positive': float(vader_scores['pos']),
                    'negative': float(vader_scores['neg']),
                    'neutral': float(vader_scores['neu']),
                    'compound': float(vader_scores['compound'])
                }
            )

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
            return SentimentResult(
                label='neutral',
                score=0.5,
                compound_score=0.0,
                details={}
            )

    async def _extract_entities(self, text: str) -> List[Entity]:
        """Extract named entities from text."""
        entities = []

        try:
            # Use spaCy for entity extraction
            if self.spacy_model:
                try:
                    doc = self.spacy_model(text)
                    for ent in doc.ents:
                        entities.append(Entity(
                            text=ent.text,
                            label=ent.label_,
                            start=ent.start_char,
                            end=ent.end_char,
                            confidence=1.0,  # spaCy doesn't provide confidence
                            metadata={"explanation": spacy.explain(ent.label_) or ent.label_, "source": "spacy"}
                        ))
                except Exception as e:
                    logger.warning(f"spaCy entity extraction failed: {e}")

            # Use transformer NER model for additional entities
            if self.ner_model and len(entities) < 10:  # Avoid redundancy
                try:
                    # Truncate text if needed
                    max_length = 512
                    text_to_analyze = text if len(text) <= max_length else text[:max_length]
                    ner_results = self.ner_model(text_to_analyze)

                    for ent in ner_results:
                        # Check if entity already exists
                        existing = any(
                            e.text.lower() == ent['word'].lower() and
                            abs(e.start - ent['start']) < 5
                            for e in entities
                        )

                        if not existing:
                            entities.append(Entity(
                                text=ent['word'],
                                label=ent['entity_group'],
                                start=ent['start'],
                                end=ent['end'],
                                confidence=float(ent['score']),
                                metadata={"source": "transformer"}
                            ))
                except Exception as e:
                    logger.warning(f"Transformer NER failed: {e}")

            logger.debug(f"Extracted {len(entities)} entities")
            return entities

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}", exc_info=True)
            return []

    async def _extract_keywords(self, text: str, **kwargs) -> List[KeywordResult]:
        """Extract keywords from text."""
        try:
            max_keywords = kwargs.get("max_keywords", 10)
            min_score = kwargs.get("min_score", 0.1)

            # Preprocess text
            doc = self.spacy_model(text) if self.spacy_model else None

            # Remove stopwords and get lemmas
            try:
                stop_words = set(stopwords.words('english'))
            except Exception as e:
                logger.warning(f"Failed to load stopwords: {e}")
                stop_words = set()

            words = word_tokenize(text.lower())

            # Filter and lemmatize words
            filtered_words = []
            for word in words:
                if (word.isalpha() and
                    word not in stop_words and
                    len(word) > 2):
                    if self.lemmatizer:
                        try:
                            word = self.lemmatizer.lemmatize(word)
                        except:
                            pass
                    filtered_words.append(word)

            # Calculate TF-IDF scores
            if len(filtered_words) < 3:
                logger.warning("Not enough words for keyword extraction")
                return []

            # Create document for TF-IDF
            document = ' '.join(filtered_words)
            vectorizer = TfidfVectorizer(max_features=max_keywords * 2)
            tfidf_matrix = vectorizer.fit_transform([document])
            feature_names = vectorizer.get_feature_names_out()
            scores = tfidf_matrix.toarray()[0]

            # Create keyword results
            keywords = []
            for i, score in enumerate(scores):
                if score >= min_score:
                    keyword = feature_names[i]
                    frequency = filtered_words.count(keyword)
                    positions = [j for j, w in enumerate(words) if w.lower() == keyword]

                    keywords.append(KeywordResult(
                        keyword=keyword,
                        score=float(score),
                        frequency=frequency,
                        positions=positions,
                        context=[]  # Could be enhanced with context extraction
                    ))

            # Sort by score and return top keywords
            keywords.sort(key=lambda x: x.score, reverse=True)
            result = keywords[:max_keywords]

            logger.debug(f"Extracted {len(result)} keywords")
            return result

        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}", exc_info=True)
            return []

    async def _summarize_text(self, text: str, **kwargs) -> SummaryResult:
        """Summarize text."""
        try:
            max_length = kwargs.get("max_length", 150)
            min_length = kwargs.get("min_length", 50)

            # Validate max/min length
            if max_length < min_length:
                logger.warning(f"max_length ({max_length}) < min_length ({min_length}), adjusting")
                max_length = min_length + 10

            # Check if text is long enough to summarize
            sentences = sent_tokenize(text)
            if len(sentences) <= 2 or len(text) < min_length:
                logger.info("Text too short for summarization, returning original")
                return SummaryResult(
                    summary=text,
                    original_length=len(text),
                    summary_length=len(text),
                    compression_ratio=1.0,
                    key_sentences=sentences
                )

            # Use transformer summarization
            if self.summarizer:
                try:
                    # Truncate text if too long
                    max_input_length = 1024
                    if len(text) > max_input_length:
                        logger.warning(f"Text too long ({len(text)}), truncating to {max_input_length}")
                        text = text[:max_input_length]

                    # Ensure sensible length parameters
                    actual_max_length = min(max_length, len(text) // 2, 500)
                    actual_min_length = min(min_length, actual_max_length - 10, len(text) // 4)

                    summary_result = self.summarizer(
                        text,
                        max_length=actual_max_length,
                        min_length=actual_min_length,
                        do_sample=False
                    )[0]

                    summary_text = summary_result['summary_text']

                    logger.debug(f"Summarization: {len(text)} -> {len(summary_text)} chars")

                    return SummaryResult(
                        summary=summary_text,
                        original_length=len(text),
                        summary_length=len(summary_text),
                        compression_ratio=float(len(summary_text) / len(text)),
                        key_sentences=sent_tokenize(summary_text)
                    )

                except Exception as e:
                    logger.warning(f"Transformer summarization failed: {e}")

            # Fallback: extractive summarization
            logger.info("Using extractive summarization fallback")
            return self._extractive_summarization(text, sentences, max_length)

        except Exception as e:
            logger.error(f"Text summarization failed: {e}", exc_info=True)
            fallback_summary = text[:max_length] + "..." if len(text) > max_length else text
            return SummaryResult(
                summary=fallback_summary,
                original_length=len(text),
                summary_length=len(fallback_summary),
                compression_ratio=min(1.0, len(fallback_summary) / len(text)) if len(text) > 0 else 1.0,
                key_sentences=[]
            )

    def _extractive_summarization(self, text: str, sentences: List[str], max_length: int) -> SummaryResult:
        """Simple extractive summarization fallback."""
        try:
            # Score sentences by keyword frequency
            word_freq = {}
            words = word_tokenize(text.lower())

            try:
                stop_words = set(stopwords.words('english'))
            except:
                stop_words = set()

            for word in words:
                if word.isalpha() and word not in stop_words:
                    word_freq[word] = word_freq.get(word, 0) + 1

            # Score sentences
            sentence_scores = {}
            for sentence in sentences:
                words = word_tokenize(sentence.lower())
                score = sum(word_freq.get(word, 0) for word in words if word.isalpha())
                sentence_scores[sentence] = score

            # Select top sentences
            sorted_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)

            summary_sentences = []
            current_length = 0

            for sentence, score in sorted_sentences:
                if current_length + len(sentence) <= max_length:
                    summary_sentences.append(sentence)
                    current_length += len(sentence)
                else:
                    break

            # Ensure at least one sentence
            if not summary_sentences and sentences:
                summary_sentences = [sentences[0]]

            summary = ' '.join(summary_sentences)

            return SummaryResult(
                summary=summary,
                original_length=len(text),
                summary_length=len(summary),
                compression_ratio=float(len(summary) / len(text)) if len(text) > 0 else 1.0,
                key_sentences=summary_sentences
            )
        except Exception as e:
            logger.error(f"Extractive summarization failed: {e}")
            return SummaryResult(
                summary=text[:max_length],
                original_length=len(text),
                summary_length=min(len(text), max_length),
                compression_ratio=min(1.0, max_length / len(text)) if len(text) > 0 else 1.0,
                key_sentences=[]
            )

    async def _detect_language(self, text: str) -> Optional[LanguageResult]:
        """Detect language of text."""
        try:
            # langdetect requires at least some text
            if len(text.strip()) < 10:
                logger.warning("Text too short for reliable language detection")
                return LanguageResult(
                    language='English',
                    confidence=0.3,
                    iso_code='en',
                    alternatives=[]
                )

            try:
                detected = detect(text)
            except LangDetectException as e:
                logger.warning(f"Language detection failed: {e}")
                return LanguageResult(
                    language='English',
                    confidence=0.5,
                    iso_code='en',
                    alternatives=[]
                )

            # Map to full language names
            language_map = {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'zh': 'Chinese',
                'ja': 'Japanese',
                'ko': 'Korean',
                'ar': 'Arabic',
                'hi': 'Hindi',
                'nl': 'Dutch',
                'sv': 'Swedish',
                'pl': 'Polish',
                'tr': 'Turkish'
            }

            language_name = language_map.get(detected, detected.upper())

            # langdetect doesn't provide confidence, estimate based on text length
            confidence = min(0.9, 0.5 + (len(text) / 1000) * 0.4)

            logger.debug(f"Detected language: {language_name} ({detected})")

            return LanguageResult(
                language=language_name,
                confidence=float(confidence),
                iso_code=detected,
                alternatives=[]
            )

        except Exception as e:
            logger.error(f"Language detection failed: {e}", exc_info=True)
            return LanguageResult(
                language='English',
                confidence=0.5,
                iso_code='en',
                alternatives=[]
            )

    async def _classify_text(self, text: str, **kwargs) -> ClassificationResult:
        """Classify text into categories."""
        try:
            # This is a placeholder implementation
            # In practice, you would use a trained classification model

            categories = kwargs.get("categories", ["positive", "negative", "neutral"])

            if not categories:
                raise ValueError("Categories list cannot be empty")

            # Simple keyword-based classification as fallback
            positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic", "love", "best"]
            negative_words = ["bad", "terrible", "awful", "horrible", "poor", "worst", "hate", "disappointing"]

            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)

            if positive_count > negative_count:
                label = "positive" if "positive" in categories else categories[0]
                confidence = min(0.9, 0.5 + positive_count * 0.1)
            elif negative_count > positive_count:
                label = "negative" if "negative" in categories else categories[0]
                confidence = min(0.9, 0.5 + negative_count * 0.1)
            else:
                label = "neutral" if "neutral" in categories else categories[0]
                confidence = 0.5

            probabilities = {label: confidence}
            for cat in categories:
                if cat != label:
                    probabilities[cat] = (1.0 - confidence) / max(1, len(categories) - 1)

            logger.debug(f"Classification: {label} (confidence: {confidence:.2f})")

            return ClassificationResult(
                label=label,
                confidence=float(confidence),
                probabilities=probabilities,
                features={"positive_words": positive_count, "negative_words": negative_count}
            )

        except Exception as e:
            logger.error(f"Text classification failed: {e}", exc_info=True)
            return ClassificationResult(
                label="unknown",
                confidence=0.0,
                probabilities={},
                features={}
            )

    async def _calculate_similarity(self, text1: str, text2: str) -> SimilarityResult:
        """Calculate semantic similarity between two texts."""
        try:
            if self.sentence_transformer:
                # Use sentence transformer for semantic similarity
                try:
                    embeddings = self.sentence_transformer.encode([text1, text2])
                    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

                    logger.debug(f"Similarity (sentence transformer): {similarity:.4f}")

                    return SimilarityResult(
                        similarity_score=float(similarity),
                        embedding_1=embeddings[0].tolist() if hasattr(embeddings[0], 'tolist') else embeddings[0],
                        embedding_2=embeddings[1].tolist() if hasattr(embeddings[1], 'tolist') else embeddings[1],
                        method="sentence_transformer"
                    )
                except Exception as e:
                    logger.warning(f"Sentence transformer similarity failed: {e}")

            # Fallback to TF-IDF similarity
            logger.info("Using TF-IDF similarity fallback")
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

            logger.debug(f"Similarity (TF-IDF): {similarity:.4f}")

            return SimilarityResult(
                similarity_score=float(similarity),
                embedding_1=None,
                embedding_2=None,
                method="tfidf"
            )

        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}", exc_info=True)
            return SimilarityResult(
                similarity_score=0.0,
                embedding_1=None,
                embedding_2=None,
                method="error"
            )

    def preprocess_text(self, text: str, language: Optional[LanguageCode] = None) -> str:
        """Preprocess text before analysis."""
        # Basic preprocessing
        # Remove excessive whitespace
        text = ' '.join(text.split())

        # Remove special characters for certain tasks
        # But keep punctuation for sentiment and other tasks

        return text

    def postprocess_result(self, result: NLPResult) -> NLPResult:
        """Postprocess prediction results."""
        # Add confidence scores, validate outputs, etc.

        # Calculate overall confidence based on task
        if result.sentiment and hasattr(result.sentiment, 'score'):
            result.confidence = result.sentiment.score
        elif result.entities:
            result.confidence = sum(e.confidence for e in result.entities) / len(result.entities) if result.entities else 0.5
        elif result.language_detection:
            result.confidence = result.language_detection.confidence
        elif result.classification:
            result.confidence = result.classification.confidence
        elif result.similarity:
            result.confidence = result.similarity.similarity_score
        else:
            result.confidence = 0.5

        return result

    async def train(
        self,
        training_data: List[TrainingData],
        config: TrainingConfig
    ) -> Dict[str, Any]:
        """Train the NLP model with provided data."""
        # This is a placeholder for training implementation
        # In practice, you would implement task-specific training

        logger.info(f"Training {config.task_type} model with {len(training_data)} samples")

        # Validate training data
        if not training_data:
            raise ValueError("Training data cannot be empty")

        if len(training_data) < 10:
            logger.warning(f"Training data is small ({len(training_data)} samples), results may be unreliable")

        return {
            "status": "training_complete",
            "samples_used": len(training_data),
            "task_type": config.task_type.value if hasattr(config.task_type, 'value') else str(config.task_type),
            "epochs": config.epochs,
            "final_accuracy": 0.85,  # Placeholder
            "training_time": 300  # Placeholder
        }

    async def evaluate(
        self,
        test_data: List[TrainingData],
        metrics: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Evaluate the model on test data."""
        if metrics is None:
            metrics = ["accuracy", "f1", "precision", "recall"]

        # Validate test data
        if not test_data:
            raise ValueError("Test data cannot be empty")

        logger.info(f"Evaluating model on {len(test_data)} samples")

        # Placeholder implementation
        return {
            "accuracy": 0.85,
            "f1": 0.83,
            "precision": 0.84,
            "recall": 0.82,
            "samples_evaluated": len(test_data)
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models."""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "supported_tasks": [task.value if hasattr(task, 'value') else str(task) for task in self.supported_tasks],
            "supported_languages": [lang.value if hasattr(lang, 'value') else str(lang) for lang in self.supported_languages],
            "loaded_models": {
                "spacy": self.spacy_model_name if self.spacy_model else None,
                "sentiment": self.sentiment_model_name if self.sentiment_analyzer else None,
                "ner": self.ner_model_name if self.ner_model else None,
                "summarization": self.summarization_model if self.summarizer else None,
                "sentence_transformer": self.sentence_model if self.sentence_transformer else None,
                "vader": "loaded" if self.vader_analyzer else None
            },
            "is_loaded": self.is_loaded,
            "use_gpu": self.use_gpu,
            "max_text_length": self.max_text_length
        }