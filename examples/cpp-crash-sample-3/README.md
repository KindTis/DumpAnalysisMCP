# cpp-crash-sample-3

이 폴더는 DumpAnalysisMCP의 멀티스레드 크래시 분석 검증을 위한 샘플입니다.  
현재 포함된 파일:

- `CppConsoleApplication.cpp`: 메인 스레드는 정상 루프를 유지하고, 서브 스레드에서 크래시를 유발하는 소스 코드
- `CppConsoleApplication.dmp`: 수집된 크래시 덤프
- `CppConsoleApplication.pdb`: 심볼 파일

## 소스 코드 설명

`CppConsoleApplication.cpp`의 핵심 흐름은 다음과 같습니다.

- `main()`에서 `SharedBuffer`를 `new`로 생성하고 데이터를 채웁니다.
- 서브 스레드(`SubThreadEntry`)를 시작하며 `SharedBuffer*` raw 포인터를 전달합니다.
- 메인 스레드는 정상 루프(`sleep_for`)를 계속 수행합니다.
- 이후 메인 스레드가 `delete buffer`를 호출해 버퍼를 먼저 해제합니다.
- 서브 스레드는 해제된 버퍼를 계속 사용하다 `DataProcessor::ConsumeData()`에서
  `m_buffer->data.data()`를 역참조/쓰기 하며 접근 위반이 발생합니다.

## 크래시 설명

이 샘플의 크래시는 의도적으로 만든 멀티스레드 `EXCEPTION_ACCESS_VIOLATION (0xC0000005)`입니다.  
근본 원인은 스레드 간 수명 관리 실패로 인한 `Use-After-Free`(댕글링 포인터)입니다.

분석 시 기대되는 핵심 정보:

- 예외 코드: `0xC0000005`
- 예외 이름: `EXCEPTION_ACCESS_VIOLATION`
- 주요 함수: `DataProcessor::ConsumeData`
- 소스 파일: `CppConsoleApplication.cpp` (PDB 원본 경로 기준으로 다른 절대 경로가 표시될 수 있음)
- 멀티스레드: 메인 스레드는 `main -> sleep_for` 대기 상태, 서브 스레드에서 크래시 유발

## MCP 테스트 용도

이 샘플은 다음 흐름을 검증하는 데 사용합니다.

- `register_dump`
- `analyze_dump`
- `get_thread_list`
- `get_thread_stack_trace`
- `get_source_context` (`source_path_map` 포함)

즉, AI Agent가 멀티스레드 덤프에서 faulting thread를 식별하고,
크래시 원인을 `Use-After-Free`로 설명하며, 소스 문맥까지 연결하는 시나리오를 검증하기 위한 데이터셋입니다.
