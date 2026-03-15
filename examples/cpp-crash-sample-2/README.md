# cpp-crash-sample-2

이 폴더는 DumpAnalysisMCP 테스트를 위한 고급 크래시 샘플입니다.  
현재 포함된 파일:

- `CppConsoleApplication.cpp`: 여러 클래스 계층과 깊은 콜스택을 포함한 크래시 재현 소스 코드
- `CppConsoleApplication.dmp`: 수집된 크래시 덤프
- `CppConsoleApplication.pdb`: 심볼 파일

## 소스 코드 설명

`CppConsoleApplication.cpp`의 핵심 흐름은 다음과 같습니다.

- `GameSession::Initialize()`에서 `Mage`에게만 아이템을 지급합니다.
- `Warrior`는 아이템 없이 전투를 시작합니다.
- `BattleManager`가 `Warrior::Charge()`를 호출하고,
- `Character::UseFirstItem()`에서 인벤토리 첫 아이템(`GetItem(0)`)을 사용하려고 시도합니다.
- 이 경로에서 인벤토리 경계/널 처리 누락으로 크래시가 발생하도록 구성되어 있습니다.

## 크래시 설명

이 샘플의 목적은 단순 단일 함수 크래시가 아니라,  
`BattleManager -> Warrior -> Character -> Inventory`로 이어지는 **깊은 콜스택**을 가진 크래시를 재현하는 것입니다.

분석 시 기대되는 핵심 정보:

- 주요 함수 체인:
  - `Inventory::GetItem`
  - `Character::UseFirstItem`
  - `Warrior::Charge`
  - `BattleManager::*`
- 문제 지점:
  - 인벤토리 범위 체크 없는 접근
  - 아이템 널 가능성 미검증

참고: 덤프 생성/분석 시점의 심볼 상태에 따라 예외 코드/최상위 fault 함수가 `ntdll` 또는 `UNKNOWN_EXCEPTION`으로 표시될 수 있습니다. 이 경우에도 스택 프레임에서 위 함수 체인을 통해 원인 추적이 가능합니다.

## MCP 테스트 용도

이 샘플은 다음 흐름을 검증하는 데 사용합니다.

- `register_dump`
- `analyze_dump`
- `get_stack_trace`
- `search_code_references`

즉, AI Agent가 깊은 콜스택에서 실제 원인 함수(`UseFirstItem`/`GetItem`)를 찾아내고, 관련 소스 라인까지 연결해 수정 전략을 도출하는 시나리오를 검증하기 위한 데이터셋입니다.
