import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError('GOOGLE_API_KEY not set')

genai.configure(api_key=GOOGLE_API_KEY)


def get_model():
    """Gemini 2.0 Flash 모델 인스턴스 반환"""
    return genai.GenerativeModel("gemini-2.0-flash")
