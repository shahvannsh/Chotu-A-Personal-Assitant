from fastapi import APIRouter
from fastapi.responses import FileResponse
from datetime import datetime

router = APIRouter()

@router.get('/')
def index():
    return FileResponse('index.html')

@router.get('/index.html')
def index_html():
    return FileResponse('index.html')

@router.get('/login.html')
def login_html():
    return FileResponse('login.html')

@router.get('/dashboard.html')
def dashboard_html():
    return FileResponse('dashboard.html')

@router.get('/study.html')
def study_html():
    return FileResponse('study.html')

@router.get('/history.html')
def history_html():
    return FileResponse('history.html')

@router.get('/notes.html')
def notes_html_page():
    return FileResponse('notes.html')

@router.get('/health')
def health():
    return {'status': 'ok', 'version': '2.0.1', 'timestamp': datetime.now().isoformat()}
