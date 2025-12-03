# setup_nlp.py - One-time NLTK data download for sentiment analysis

import nltk
import ssl

# Fix SSL certificate for NLTK downloads (university networks)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

print("📥 Downloading NLTK models... (one-time only)")

# Required NLTK data for sentiment analysis
nltk.download('punkt')
nltk.download('vader_lexicon')
nltk.download('averaged_perceptron_tagger')
nltk.download('maxent_ne_chunker')
nltk.download('words')

print("✅ NLTK models downloaded successfully!")
print("🔄 Add to .gitignore: nltk_data/")
