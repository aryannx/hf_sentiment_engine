# test_imports.py - Fixed version

packages = [
    "pandas as pd",
    "numpy",
    "yfinance as yf",
    "backtrader as bt",
    "transformers",  # Fixed
    "torch",
    "streamlit",
    "plotly",
    "nltk",
    "sklearn",  # Fixed scikit-learn alias
    "textblob"
]

success_count = 0
errors = []
for pkg in packages:
    try:
        exec(f"import {pkg}")
        print(f"✅ {pkg}")
        success_count += 1
    except ImportError as e:
        print(f"❌ {pkg}: {e}")
        errors.append(pkg)

print(f"\n🎉 {success_count}/{len(packages)} packages OK!")

if errors:
    print("\n🔧 Fix errors:")
    for pkg in errors:
        print(f"  pip install {pkg} --upgrade")
