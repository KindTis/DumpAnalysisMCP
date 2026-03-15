# cpp-crash-sample-4

이 폴더는 DumpAnalysisMCP의 복합 시나리오 크래시 분석 검증을 위한 샘플입니다.  
현재 포함된 파일:

- `CppConsoleApplication.cpp`: 프로그램 진입점 및 크래시 타이밍 제어
- `CppConsoleApplication.dmp`: 수집된 크래시 덤프
- `CppConsoleApplication.pdb`: 심볼 파일
- `Core/`, `Engine/`, `Game/`: 계층 구조를 가진 샘플 코드베이스

## 소스 코드 설명

이 샘플의 핵심 흐름은 다음과 같습니다.

- `main()`에서 `GameWorld`를 생성하고 AI 워커 스레드를 시작합니다.
- AI 스레드는 `AIController::Tick()`을 주기적으로 실행하며 전투 계산을 수행합니다.
- 호출 체인은 대략 다음과 같습니다.
  - `AIController::Tick`
  - `CombatSystem::UpdateCombat`
  - `CombatSystem::ComputeShotOrigin`
  - `NavigationSystem::BuildAimingSolution`
  - `Character::GetHeadSocketPosition`
  - `SkeletalMeshComponent::GetSocketWorldPosition`
- 메인 스레드는 300ms 후 `GameWorld::UnloadStreamingLevel()`을 호출합니다.
- 이 과정에서 `Character::DestroyForLevelStreaming()`이 실행되어:
  - `transform_`을 해제하고
  - `mesh_->InvalidateOwnerTransform()`으로 `ownerTransform_`를 `nullptr`로 무효화합니다.
- 이후 AI 워커 스레드가 계속 `GetSocketWorldPosition()`을 호출하면,
  `ownerTransform_->GetWorldPosition()`에서 접근 위반이 발생합니다.

## 크래시 설명

이 샘플의 크래시는 의도적으로 만든 멀티스레드 `EXCEPTION_ACCESS_VIOLATION (0xC0000005)`입니다.  
근본 원인은 레벨 스트리밍 언로드 시점과 AI 업데이트 시점이 충돌하면서 발생한
**수명/동기화 관리 누락(무효 포인터 역참조)**입니다.

분석 시 기대되는 핵심 정보:

- 예외 코드: `0xC0000005`
- 예외 이름: `EXCEPTION_ACCESS_VIOLATION`
- 주요 크래시 함수: `SkeletalMeshComponent::GetSocketWorldPosition`
- 연관 함수 체인:
  - `Character::GetHeadSocketPosition`
  - `NavigationSystem::BuildAimingSolution`
  - `CombatSystem::ComputeShotOrigin` / `UpdateCombat`
  - `AIController::Tick`
- 멀티스레드 관찰:
  - 메인 스레드: 언로드/종료 흐름 담당
  - 워커 스레드: 전투 계산 루프 중 크래시

## MCP 테스트 용도

이 샘플은 다음 흐름을 검증하는 데 사용합니다.

- `register_dump`
- `analyze_dump`
- `get_thread_list`
- `get_thread_stack_trace`
- `get_source_context`
- `search_code_references`

즉, AI Agent가 복합 계층 호출 스택에서 실제 fault 지점을 추적하고,
멀티스레드 관점(메인 언로드 vs 워커 업데이트)을 함께 설명하는 시나리오를 검증하기 위한 데이터셋입니다.
