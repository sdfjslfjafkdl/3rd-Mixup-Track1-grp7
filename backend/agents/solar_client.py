"""
Solar Pro3 API 클라이언트
OpenAI 호환 인터페이스로 Upstage Solar Pro3에 접근

API Spec:
- Base URL: https://api.upstage.ai/v1
- Model: solar-pro3
- Tool Calling: OpenAI 호환 (tools 파라미터)
"""
from openai import OpenAI
from typing import Any, Dict, List, Optional
import json
import sys
import os

# config 모듈 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import SOLAR_API_KEY, SOLAR_MODEL, SOLAR_API_BASE_URL

class SolarClient:
    """Solar Pro3 Agent 클라이언트"""
    
    def __init__(self):
        """Solar Pro3 클라이언트 초기화"""
        self.client = OpenAI(
            api_key=SOLAR_API_KEY,
            base_url=SOLAR_API_BASE_URL
        )
        self.model = SOLAR_MODEL
        print(f"✅ [SolarClient] 초기화 완료")
        print(f"   - Base URL: {SOLAR_API_BASE_URL}")
        print(f"   - Model: {SOLAR_MODEL}")
    
    def simple_chat(self, message: str) -> str:
        """
        간단한 채팅 (tool calling 없음)
        STEP 1 테스트용: 서버가 응답하는지 확인
        
        Args:
            message: 사용자 메시지
            
        Returns:
            응답 텍스트
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"❌ [SolarClient] 오류: {str(e)}")
            raise

    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        시스템 프롬프트를 포함한 일반 채팅

        Args:
            message: 사용자 메시지
            system_prompt: 역할/출력 형식을 지정하는 시스템 프롬프트

        Returns:
            응답 텍스트
        """
        try:
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            messages.append({
                "role": "user",
                "content": message
            })

            request_kwargs = {
                "model": self.model,
                "messages": messages,
            }
            if max_tokens is not None:
                request_kwargs["max_tokens"] = max_tokens

            response = self.client.chat.completions.create(**request_kwargs)
            return response.choices[0].message.content or ""

        except Exception as e:
            print(f"❌ [SolarClient] 오류: {str(e)}")
            raise
    
    def chat_with_tools(
        self, 
        message: str, 
        tools: List[Dict[str, Any]], 
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tool calling 기능이 있는 채팅
        Agent가 필요한 도구를 선택해서 호출하도록 유도
        
        Args:
            message: 사용자 메시지
            tools: 사용 가능한 tool 정의 목록
            system_prompt: 시스템 프롬프트 (Agent 역할 정의)
            
        Returns:
            응답 객체 (role, content, tool_calls 등)
        """
        try:
            messages = []
            
            # 시스템 프롬프트 추가 (있으면)
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            # 사용자 메시지
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Tool calling 요청
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto"  # Agent가 필요할 때만 tool 선택
            )
            
            # 응답 처리
            result = {
                "role": response.choices[0].message.role,
                "content": response.choices[0].message.content,
                "tool_calls": []
            }
            
            # Tool calling이 있으면 추가
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    })
            
            return result
            
        except Exception as e:
            print(f"❌ [SolarClient] 오류: {str(e)}")
            raise


# STEP 1 테스트 함수
def test_simple_chat():
    """간단한 채팅 테스트"""
    print("\n" + "="*60)
    print("STEP 1: Solar Pro3 연결 테스트")
    print("="*60)
    
    try:
        client = SolarClient()
        
        print("\n📤 요청: '안녕, 너 누구야?'")
        response = client.simple_chat("안녕, 너 누구야?")
        
        print(f"\n📥 응답:")
        print(f"{response}")
        
        print("\n✅ STEP 1 성공! Solar Pro3가 정상 응답합니다.")
        return True
        
    except Exception as e:
        print(f"\n❌ STEP 1 실패: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_simple_chat()
    exit(0 if success else 1)
