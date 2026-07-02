# Windows Task Scheduler 등록 절차 (M6)

무인 자동 전송을 위해 `run_transfer.bat` 을 지정 시각에 실행하도록 등록한다.

## 사전 준비
- `.env` 의 `VPN_AUTOMANAGE=1`, `OPENVPN_EXE`, `OVPN_CONFIG` 를 실제 값으로 설정.
- 수동으로 `python -m scheduler.run_transfer` 가 한 번 정상 동작하는지 먼저 확인.

## 등록
1. `scheduler/run_transfer.bat` 준비 (이미 포함됨).
   - 내용: 프로젝트 루트로 이동 후 `python -m scheduler.run_transfer`
2. **작업 스케줄러** 열기 → **작업 만들기**(기본 작업 아님, 권한 옵션이 필요).
3. **일반** 탭
   - 이름: `recording-pipeline-transfer`
   - **"사용자가 로그온했는지 여부에 관계없이 실행"** 선택
   - **"가장 높은 수준의 권한으로 실행"** 체크
4. **트리거** 탭 → 새로 만들기
   - 매일 지정 시각(예: 03:00)
5. **동작** 탭 → 새로 만들기
   - 프로그램/스크립트: `C:\Users\User\Desktop\pipeline\scheduler\run_transfer.bat`
   - 시작 위치: `C:\Users\User\Desktop\pipeline`
6. **조건/설정** 탭
   - 필요 시 "AC 전원일 때만" 해제(노트북 배터리 대응)
   - "작업이 실패하면 다시 시작" 옵션으로 재시도 보강 가능
7. 저장 시 계정 비밀번호 입력.

## 검증
- 작업을 **마우스 우클릭 → 실행**으로 즉시 트리거하여 `logs/pipeline.log`, `logs/scheduler.out` 확인.
- 이미 `sent/` 로 옮겨진 세션은 재전송되지 않음(idempotent) 확인.

> VPN 자동관리를 끄고(=0) 운영한다면, VPN 이 이미 연결된 상태에서만 이 작업이 성공한다.
> 이 경우 OpenVPN 을 서비스/부팅 자동연결로 상시 유지하는 구성을 권장.
