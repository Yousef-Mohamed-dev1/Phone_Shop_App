import flet as ft
import flet.fastapi as flet_fastapi
import sys
import os

# إضافة المجلد الرئيسي لمسار المكتبات
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main

# تصدير المتغير app في المستوى الرئيسي المطلق لـ Vercel
app = flet_fastapi.app(main)