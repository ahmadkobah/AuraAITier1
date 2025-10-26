import os
from typing import Dict, Any, Optional
from pathlib import Path
import json

class NLPConfig:
    """Configuration manager for NLP service."""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables and config files."""
        config = {
            # Service configuration
            "service": {
                "host": os.getenv("NLP_HOST", "0.0.0.0"),
                "port": int(os.getenv("NLP_PORT", "8002")),
                "workers": int(os.getenv("NLP_WORKERS", "1")),
                "log_level": os.getenv("LOG_LEVEL", "INFO"),
                "debug": os.getenv("DEBUG", "false").lower() == "true"
            },
            
            # Model paths and configurations
            "models": {
                "base_path": os.getenv("NLP_MODEL_PATH", "./models"),
                "sentiment_model": os.getenv("SENTIMENT_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest"),
                "ner_model": os.getenv("NER_MODEL", "dbmdz/bert-large-cased-finetuned-conll03-english"),
                "summarization_model": os.getenv("SUMMARIZATION_MODEL", "facebook/bart-large-cnn"),
                "sentence_model": os.getenv("SENTENCE_MODEL", "all-MiniLM-L6-v2"),
                "spacy_model": os.getenv("SPACY_MODEL", "en_core_web_sm"),
                "cache_dir": os.getenv("TRANSFORMERS_CACHE", "./models/cache")
            },
            
            # Training configuration
            "training": {
                "data_path": os.getenv("TRAINING_DATA_PATH", "./training_data"),
                "batch_size": int(os.getenv("TRAINING_BATCH_SIZE", "16")),
                "learning_rate": float(os.getenv("TRAINING_LEARNING_RATE", "1e-5")),
                "epochs": int(os.getenv("TRAINING_EPOCHS", "10")),
                "validation_split": float(os.getenv("VALIDATION_SPLIT", "0.2")),
                "early_stopping": os.getenv("EARLY_STOPPING", "true").lower() == "true"
            },
            
            # Processing limits
            "limits": {
                "max_text_length": int(os.getenv("MAX_TEXT_LENGTH", "10000")),
                "max_batch_size": int(os.getenv("MAX_BATCH_SIZE", "100")),
                "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "300")),
                "max_summary_length": int(os.getenv("MAX_SUMMARY_LENGTH", "500")),
                "min_summary_length": int(os.getenv("MIN_SUMMARY_LENGTH", "10"))
            },
            
            # Language support
            "languages": {
                "supported": os.getenv("SUPPORTED_LANGUAGES", "en,es,fr,de,it,pt,ru,zh").split(","),
                "default": os.getenv("DEFAULT_LANGUAGE", "en"),
                "auto_detect": os.getenv("AUTO_DETECT", "true").lower() == "true"
            },
            
            # Performance settings
            "performance": {
                "cache_enabled": os.getenv("CACHE_ENABLED", "true").lower() == "true",
                "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),
                "use_gpu": os.getenv("USE_GPU", "false").lower() == "true",
                "gpu_device": int(os.getenv("GPU_DEVICE", "0")),
                "model_precision": os.getenv("MODEL_PRECISION", "float32"),
                "optimize_models": os.getenv("OPTIMIZE_MODELS", "false").lower() == "true"
            },
            
            # Quality settings
            "quality": {
                "min_confidence": float(os.getenv("MIN_CONFIDENCE", "0.1")),
                "confidence_threshold": float(os.getenv("CONFIDENCE_THRESHOLD", "0.5")),
                "quality_check": os.getenv("QUALITY_CHECK", "true").lower() == "true",
                "validate_inputs": os.getenv("VALIDATE_INPUTS", "true").lower() == "true"
            },
            
            # API settings
            "api": {
                "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
                "rate_limit": int(os.getenv("RATE_LIMIT", "100")),
                "rate_limit_window": int(os.getenv("RATE_LIMIT_WINDOW", "60")),
                "max_file_size": int(os.getenv("MAX_FILE_SIZE", "10485760")),  # 10MB
                "allowed_file_types": os.getenv("ALLOWED_FILE_TYPES", "txt,json,csv").split(",")
            },
            
            # Monitoring and logging
            "monitoring": {
                "metrics_enabled": os.getenv("METRICS_ENABLED", "true").lower() == "true",
                "health_check_interval": int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
                "log_requests": os.getenv("LOG_REQUESTS", "true").lower() == "true",
                "log_responses": os.getenv("LOG_RESPONSES", "false").lower() == "true",
                "performance_monitoring": os.getenv("PERFORMANCE_MONITORING", "true").lower() == "true"
            }
        }
        
        # Load additional config from file if present
        config_file = os.getenv("NLP_CONFIG_FILE", "config.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    self._merge_config(config, file_config)
            except Exception as e:
                print(f"Warning: Failed to load config file {config_file}: {e}")
        
        return config
    
    def _merge_config(self, base_config: Dict[str, Any], file_config: Dict[str, Any]):
        """Merge file configuration with base configuration."""
        for key, value in file_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_model_config(self) -> Dict[str, str]:
        """Get model configuration dictionary."""
        return self.config.get("models", {})
    
    def get_training_config(self) -> Dict[str, Any]:
        """Get training configuration dictionary."""
        return self.config.get("training", {})
    
    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance configuration dictionary."""
        return self.config.get("performance", {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration dictionary."""
        return self.config.get("api", {})
    
    def is_gpu_enabled(self) -> bool:
        """Check if GPU processing is enabled."""
        return self.get("performance.use_gpu", False)
    
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.get("performance.cache_enabled", True)
    
    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return self.get("languages.supported", ["en"])
    
    def get_max_text_length(self) -> int:
        """Get maximum allowed text length."""
        return self.get("limits.max_text_length", 10000)
    
    def get_model_paths(self) -> Dict[str, Optional[str]]:
        """Get full paths for all models."""
        base_path = Path(self.get("models.base_path", "./models"))
        models = self.get_model_config()
        
        return {
            "base_path": str(base_path),
            "sentiment_model": models.get("sentiment_model"),
            "ner_model": models.get("ner_model"),
            "summarization_model": models.get("summarization_model"),
            "sentence_model": models.get("sentence_model"),
            "spacy_model": models.get("spacy_model"),
            "cache_dir": str(base_path / "cache")
        }
    
    def setup_directories(self):
        """Create necessary directories."""
        base_path = Path(self.get("models.base_path", "./models"))
        training_path = Path(self.get("training.data_path", "./training_data"))
        cache_path = Path(self.get("models.cache_dir", "./models/cache"))
        
        for path in [base_path, training_path, cache_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def validate_config(self) -> list:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check required directories
        base_path = Path(self.get("models.base_path", "./models"))
        if not base_path.exists():
            issues.append(f"Model base path does not exist: {base_path}")
        
        # Check numeric values
        max_text_length = self.get("limits.max_text_length", 10000)
        if max_text_length <= 0:
            issues.append("max_text_length must be positive")
        
        batch_size = self.get("training.batch_size", 16)
        if batch_size <= 0:
            issues.append("training batch_size must be positive")
        
        # Check language codes
        supported_languages = self.get_supported_languages()
        if not supported_languages:
            issues.append("At least one supported language must be specified")
        
        return issues
    
    def to_dict(self) -> Dict[str, Any]:
        """Return full configuration as dictionary."""
        return self.config.copy()
    
    def save_config(self, filepath: str):
        """Save current configuration to file."""
        with open(filepath, 'w') as f:
            json.dump(self.config, f, indent=2)

# Global configuration instance
config = NLPConfig()

# Environment-specific configurations
DEVELOPMENT_CONFIG = {
    "service": {
        "debug": True,
        "log_level": "DEBUG"
    },
    "performance": {
        "cache_enabled": False,
        "optimize_models": False
    }
}

PRODUCTION_CONFIG = {
    "service": {
        "debug": False,
        "log_level": "INFO"
    },
    "performance": {
        "cache_enabled": True,
        "optimize_models": True
    },
    "monitoring": {
        "log_requests": False,
        "log_responses": False
    }
}

def get_config() -> NLPConfig:
    """Get the global configuration instance."""
    return config

def setup_environment_config():
    """Setup configuration based on environment."""
    env = os.getenv("NODE_ENV", "development").lower()
    
    if env == "production":
        config._merge_config(config.config, PRODUCTION_CONFIG)
    elif env == "development":
        config._merge_config(config.config, DEVELOPMENT_CONFIG)
    
    # Setup directories
    config.setup_directories()
    
    # Validate configuration
    issues = config.validate_config()
    if issues:
        print("Configuration validation issues:")
        for issue in issues:
            print(f"  - {issue}")

if __name__ == "__main__":
    # Example usage
    setup_environment_config()
    print("NLP Service Configuration:")
    print(f"Service port: {config.get('service.port')}")
    print(f"Max text length: {config.get_max_text_length()}")
    print(f"Supported languages: {config.get_supported_languages()}")
    print(f"GPU enabled: {config.is_gpu_enabled()}")
    print(f"Cache enabled: {config.is_cache_enabled()}")