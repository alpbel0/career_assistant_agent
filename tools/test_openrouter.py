"""
OpenRouter Connection Test Script

Bu script OpenRouter API bağlantısını test eder.
Container içinden httpx kullanarak doğrudan HTTP request yapar.

Kullanım:
    python -m tools.test_openrouter
"""

import os
import sys


def test_openrouter():
    """OpenRouter API bağlantısını test eder."""

    # API key kontrolü
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ HATA: OPENROUTER_API_KEY environment variable tanımlı değil")
        print("   .env dosyasını kontrol edin")
        return False

    if api_key.startswith("sk-or-...") or api_key == "your_openrouter_api_key_here":
        print("❌ HATA: OPENROUTER_API_KEY placeholder değer")
        print("   Gerçek API key'i .env dosyasına ekleyin")
        return False

    print(f"✅ API Key mevcut (uzunluk: {len(api_key)})")

    # HTTP ile bağlantı testi
    try:
        import httpx

        print("✅ httpx modülü yüklü")

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/alpbel0/career_assistant_agent",
                "X-Title": "Career Assistant AI Agent",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Say 'test' if you can read this."}
                ],
                "max_tokens": 10,
            },
            timeout=30.0
        )

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            model = data.get("model", "unknown")
            usage = data.get("usage", {})

            print("✅ API başarılı yanıt verdi")
            print(f"   Yanıt: '{content}'")
            print(f"   Model: {model}")
            print(f"   Usage: prompt={usage.get('prompt_tokens', 0)}, "
                  f"completion={usage.get('completion_tokens', 0)}, "
                  f"total={usage.get('total_tokens', 0)}")
            return True
        else:
            print(f"❌ HATA: HTTP {response.status_code}")
            print(f"   {response.text}")
            return False

    except ImportError:
        print("❌ HATA: httpx modülü bulunamadı")
        print("   'pip install httpx' komutunu çalıştırın")
        return False
    except Exception as e:
        print(f"❌ HATA: {type(e).__name__}: {e}")
        return False


def main():
    print("=== OpenRouter Connection Test ===\n")
    success = test_openrouter()
    print(f"\nSonuç: {'BAŞARILI ✅' if success else 'BAŞARISIZ ❌'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
