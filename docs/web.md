# 웹 버전 실행 가이드

Next.js(프론트) + FastAPI(백엔드) 구조의 웹 버전.
기존 데스크톱 앱과 동일한 코어(`src/core`)를 사용한다.

## docker-compose로 실행 (권장)

```bash
docker compose up -d --build
```

- 접속: http://localhost:3000
- 백엔드 API: http://localhost:8000 (문서: http://localhost:8000/docs)
- 로그인 정보/설정은 `./data/config.*.json`에 저장되어 재시작 후에도 유지된다.
- 종료: `docker compose down`

매크로가 도는 동안에는 컨테이너(= 컴퓨터)가 켜져 있어야 한다.
예매 성공 후 결제는 SRT/코레일 앱·웹에서 결제 기한 내에 직접 해야 한다.

## 개발 모드로 실행

```bash
# 백엔드 (프로젝트 루트)
venv311/bin/pip install -r requirements-server.txt
venv311/bin/uvicorn server.app:app --reload --port 8000

# 프론트엔드
cd web && npm install && npm run dev   # http://localhost:3000
```

프론트가 다른 주소의 백엔드를 봐야 하면 `NEXT_PUBLIC_API_BASE` 환경변수로
지정한다 (기본값 `http://localhost:8000`).

## 구조

```
server/app.py      FastAPI — src/core 매니저/워커를 REST API로 노출
web/               Next.js 15 (App Router) 단일 페이지 UI
docker-compose.yml backend(8000) + frontend(3000)
```

상태는 백엔드 프로세스 메모리에 있는 단일 세션(로컬 1인용)이며,
프론트는 1초 간격 상태 폴링 + 0.7초 간격 로그 폴링으로 동기화한다.
