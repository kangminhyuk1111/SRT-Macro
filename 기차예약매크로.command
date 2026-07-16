#!/bin/bash
# 더블클릭하면 SRT/KTX 예약 매크로 런처가 실행됩니다.
# 항상 아래 프로젝트 폴더의 최신 소스(main.py)를 실행합니다.
PROJECT="/Users/kangminhyuk/IdeaProjects/srtMacro"
cd "$PROJECT"
exec "$PROJECT/venv311/bin/python" main.py
