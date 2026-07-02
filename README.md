# recording-pipeline

교육장 영상 데이터 수집 파이프라인.
**카메라(RTSP) → go2rtc → 백엔드가 무손실 MP4로 저장(세션 단위) → 무손실 압축 + SHA-256 → VPN 경유 SFTP → 회사 NAS.**

- 녹화 주체는 **백엔드(서버)**. 브라우저는 라이브뷰 표시 전용.
- 영상은 **재인코딩 금지** — go2rtc 의 remux MP4 를 그대로 파일로 기록.
- 세션 = 녹화 시작~중지 한 묶음. 세션마다 폴더 하나(영상 + `packet.json` + `checksums.sha256`).
- 전송은 스케줄러가 지정 시각에 무인 실행하며 **idempotent**(성공분만 `sent/` 이동, 실패분은 다음 주기 재시도).

---

## 1. 구성요소

| 구성 | 역할 | 접근 |
|---|---|---|
| go2rtc | 카메라 RTSP fan-out + 무손실 remux MP4 제공 | http://localhost:1984 |
| FastAPI 백엔드 | 녹화 제어 / 저장 / 압축 / 전송 | http://localhost:8000 |
| 웹 페이지 | 라이브뷰 + 시작/중지 | 브라우저 |

## 2. 디렉토리

```
recording-pipeline/
├─ go2rtc.yaml            # 카메라 스트림 정의
├─ .env / .env.example    # 설정값(비밀·경로 분리)
├─ requirements.txt
├─ backend/
│  ├─ config.py           # .env 로드
│  ├─ logutil.py          # 파일+콘솔 로거
│  ├─ recorder.py         # 카메라당 1스레드 녹화(stream.mp4 → 디스크)
│  ├─ main.py             # FastAPI: /cameras /start /stop /status
│  ├─ session.py          # 세션 폴더 확정 + packet.json + checksums
│  ├─ archive.py          # 무손실 ZIP + SHA-256
│  ├─ vpn.py              # VPN 자동 연결/해제(+도달성 확인)
│  └─ transfer.py         # SFTP 업로드 + 무결성 검증 + sent 이동
├─ scheduler/
│  ├─ run_transfer.py     # 무인 배치(압축→VPN→전송→검증→해제)
│  ├─ run_transfer.bat
│  └─ task_setup.md       # Task Scheduler 등록 절차
├─ web/index.html         # 라이브뷰 + 제어
├─ recordings/ (sent/)    # 세션 저장 / 전송완료 분리 (git 제외)
└─ logs/                  # 로그 (git 제외)
```

## 3. 설치

```powershell
# 1) 파이썬 의존성
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2) go2rtc 바이너리 내려받아 프로젝트 루트에 두고 실행
#    https://github.com/AlexxIT/go2rtc/releases
.\go2rtc.exe            # go2rtc.yaml 자동 로드, http://localhost:1984

# 3) 환경설정: .env.example 복사 후 값 채우기
copy .env.example .env  # 또는 제공된 .env 사용
```

## 4. go2rtc 설정

`go2rtc.yaml` 의 `streams` 키가 곧 카메라 ID 이며 `.env` 의 `CAMERAS` 와 이름이 일치해야 한다.

```yaml
streams:
  cam_1: rtsp://<user>:<pass>@<카메라IP>:554/stream   # 실제 CCTV
  # cam_1: ffmpeg:device?video=0#video=h264           # 개발용 웹캠(Windows)
```

브라우저에서 `http://localhost:1984` 대시보드로 각 스트림의 정확한 재생 경로를 확인할 수 있다.

## 5. 실행

```powershell
# go2rtc 를 먼저 띄운 상태에서
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 **http://localhost:8000** → 라이브뷰 확인, `녹화 시작/중지`.
중지 시 `recordings/<시작__종료>/` 폴더가 확정된다.

## 6. 저장 구조

```
recordings/20260701_140000__20260701_140530/
├─ cam_1.mp4            # 카메라 원본 코덱 그대로 (재인코딩 X)
├─ packet.json         # 세션 메타 + 마네킹 패킷 자리(빈 배열)
└─ checksums.sha256    # 폴더 내 파일 무결성
```

`packet.json`:
```json
{
  "session_start": "2026-07-01T14:00:00",
  "session_end":   "2026-07-01T14:05:30",
  "cameras":       ["cam_1"],
  "manikin_packets": []
}
```
> `manikin_packets` 는 현재 빈 배열. 추후 마네킹 패킷을 이 배열에 병합한다.

## 7. 전송 (스케줄러)

무인 배치: **압축 → VPN 연결 → SFTP 업로드 → SHA-256 검증 → sent/ 이동 → VPN 해제.**

```powershell
# 수동 1회 실행 (VPN 연결 상태에서)
python -m scheduler.run_transfer
```

- `.env` 의 `VPN_AUTOMANAGE=0` → VPN 이 이미 연결됐다고 가정(M5 수동 검증).
- `VPN_AUTOMANAGE=1` → 스케줄러가 OpenVPN 을 직접 연결/해제(M6 무인).
- Windows Task Scheduler 등록은 [scheduler/task_setup.md](scheduler/task_setup.md) 참고.

**무결성 검증**: 업로드 후 원격에서 `sha256sum` 을 실행해 로컬 해시와 대조한다.
원격이 `sha256sum` 을 지원하지 않으면 크기 검증으로 폴백하고 로그에 남긴다.

**보관 정책 / idempotent**: 성공한 세션은 **zip 만** `recordings/sent/` 에 남기고 원본
폴더는 삭제한다(무손실이라 zip 으로 복구 가능, 디스크·중복 절약). 실패분은 원본 폴더가
`recordings/` 에 그대로 남아 다음 주기에 재시도된다. zip 은 전송 중에만 잠깐 만들어졌다
성공 시 `sent/` 로, 실패 시 삭제되므로 `recordings/` 최상단에는 **전송 대기 폴더만** 보인다.

```
recordings/
├─ 20260702_140000__140530/     # 전송 대기 세션(폴더만)
└─ sent/
   └─ 20260702_139...__.zip     # 전송 완료(zip 한 개만 보관)
```

## 8. 내부망 → 외부망 이관 (M7~M9)

코드 변경 없이 `.env` 만 교체한다.

| 단계 | 바꾸는 값 |
|---|---|
| M5 인턴 PC(사내망) | `pipetest1`, `.ovpn remote = 내부 IP(192.168.0.x)` |
| M9 노트북(외부망/핫스팟) | `pipetest2`, `.ovpn remote = dallgoo.synology.me 1194` |

`SFTP_HOST` 는 VPN 터널 주소 `10.8.0.1` 로 **어디서든 고정**(하드코딩 이유). 사내/외부 구분은
`.ovpn` 의 `remote` 로만 가른다(헤어핀 NAT 회피).

## 9. 보안

- 개인키·`.env`·녹화물은 `.gitignore` 로 제외. 개인키는 해당 PC 에만 보관, NAS 엔 공개키만 등록.
- 전송 계정은 지정 폴더 읽기/쓰기 **최소 권한**만 사용.
- SFTP·SMB·DSM 포트는 인터넷 미노출. 진입은 VPN(UDP 1194) 단일 경로.

## 10. 마일스톤 (M1~M9)

M1 라이브뷰 · M2 녹화 저장 · M3 packet.json · M4 압축+체크섬 ·
M5 SFTP 전송·검증·재시도 · M6 Task Scheduler 무인 · M7 노트북 이관 ·
M8 핫스팟(내부망 차단) · M9 DDNS 외부망 전송. 반드시 순서대로 완료 기준을 통과시키며 진행.
