"""Quick test to check which packages are available"""
import sys

packages_status = {}

# Test critical packages
test_packages = [
    'spacy', 'transformers', 'torch',
    'fastapi', 'nltk', 'langdetect', 'textblob',
    'vaderSentiment', 'sklearn', 'pandas', 'numpy'
]

# Test each package
for pkg in test_packages:
    try:
        __import__(pkg)
        packages_status[pkg] = 'INSTALLED'
    except ImportError:
        packages_status[pkg] = 'MISSING'
    except Exception as e:
        packages_status[pkg] = f'ERROR: {str(e)[:50]}'

# Test sentence_transformers separately (has Keras issues)
try:
    import sentence_transformers
    packages_status['sentence_transformers'] = 'INSTALLED'
except ImportError:
    packages_status['sentence_transformers'] = 'MISSING'
except Exception as e:
    packages_status['sentence_transformers'] = f'ERROR: {str(e)[:50]}'

print("Package Status Report:")
print("=" * 50)
for pkg, status in packages_status.items():
    if status == 'INSTALLED':
        symbol = "OK"
    elif status == 'MISSING':
        symbol = "MISSING"
    else:
        symbol = "ERROR"
    print(f"[{symbol}] {pkg}: {status}")

installed_count = sum(1 for s in packages_status.values() if s == 'INSTALLED')
missing_count = sum(1 for s in packages_status.values() if s == 'MISSING')
error_count = sum(1 for s in packages_status.values() if s not in ['INSTALLED', 'MISSING'])

print(f"\nTotal: {len(packages_status)} packages")
print(f"  - Installed: {installed_count}")
print(f"  - Missing: {missing_count}")
print(f"  - Errors: {error_count}")
