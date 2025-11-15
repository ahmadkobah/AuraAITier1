"""
Direct test of DeepSeek OCR model loading with Hugging Face
"""
import torch

print("=" * 60)
print("Testing DeepSeek OCR Model Loading (Hugging Face)")
print("=" * 60)

# Check CUDA
print(f"\n✅ CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    print(f"✅ CUDA Version: {torch.version.cuda}")

# Try to import transformers
print("\n📦 Importing transformers...")
try:
    from transformers import AutoModel, AutoTokenizer
    print("✅ transformers imported successfully")
except Exception as e:
    print(f"❌ Failed to import transformers: {e}")
    exit(1)

# Try to load the model
model_name = "deepseek-ai/DeepSeek-OCR"
print(f"\n📥 Loading model: {model_name}")
print("   (This may take a while on first run...)")

try:
    print("   Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True
    )
    print("   ✅ Tokenizer loaded!")
    
    print("   Loading model...")
    model = AutoModel.from_pretrained(
        model_name,
        trust_remote_code=True,
        use_safetensors=True,
        attn_implementation="eager"  # Use eager attention instead of flash_attention_2
    )
    print("   ✅ Model loaded!")
    
    # Move to GPU
    if torch.cuda.is_available():
        print("   Moving to GPU...")
        model = model.eval().cuda().to(torch.bfloat16)
        print("   ✅ Model on GPU!")
    else:
        model = model.eval()
        print("   ⚠️ Model on CPU")
    
    print("\n✅ SUCCESS! DeepSeek OCR model loaded with Hugging Face!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ FAILED to load model: {e}")
    import traceback
    traceback.print_exc()
    print("=" * 60)
