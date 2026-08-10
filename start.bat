@echo off
chcp 65001 > nul
echo ==============================================
echo   AutoPost AI - SNS 자동 발행 시스템
echo ==============================================

echo [1/3] 가상환경(venv) 확인 및 활성화...
if not exist venv (
    echo 가상환경이 없습니다. 새로 생성합니다...
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [2/3] 필수 패키지 설치...
pip install -r requirements.txt

echo [3/3] 서버를 시작합니다... (http://localhost:5000)
python app.py
pause
