"""
Solar Pro3 간단 테스트 (공식 예시 기반)
"""
from openai import OpenAI

# API 키와 URL 직접 입력
api_key = "up_2hMlWqAkIgXnmAVJni85IZX3inFMH"
base_url = "https://api.upstage.ai/v1"

print("="*60)
print("STEP 1: Solar Pro3 연결 테스트")
print("="*60)
print(f"\nBase URL: {base_url}")
print(f"Model: solar-pro-3")

try:
    print("\n[1] OpenAI 클라이언트 초기화 중...")
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    print("✅ 클라이언트 초기화 성공")
    
    print("\n[2] Chat API 요청 중...")
    print("📤 요청: '안녕, 너 누구야?'")
    
    response = client.chat.completions.create(
        model="solar-pro3",
        messages=[
            {
                "role": "user",
                "content": "안녕, 너 누구야?"
            }
        ]
    )
    
    print("\n📥 응답:")
    print(response.choices[0].message.content)
    
    print("\n✅ STEP 1 성공!")
    
except Exception as e:
    print(f"\n❌ 오류: {type(e).__name__}")
    print(f"   {str(e)}")
    import traceback
    traceback.print_exc()
