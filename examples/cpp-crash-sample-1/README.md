# cpp-crash-sample

이 폴더는 DumpAnalysisMCP 테스트를 위한 최소 크래시 샘플입니다.
현재 포함된 파일:

- `main.cpp`: 크래시를 의도적으로 발생시키는 소스 코드
- `cpp_crash_sample.dmp`: 수집된 크래시 덤프
- `cpp_crash_sample.pdb`: 심볼 파일

## 소스 코드 설명

`main.cpp`의 핵심 흐름은 다음과 같습니다.

- `main()`에서 시작 메시지를 출력하고 2초 대기합니다.
- 이후 `TriggerAccessViolation()`을 호출합니다.
- `TriggerAccessViolation()`에서 `volatile int* ptr = nullptr;`로 널 포인터를 만든 뒤
  `*ptr = 42;`를 수행해 쓰기 접근 위반(Access Violation)을 발생시킵니다.

## 크래시 설명

이 샘플의 크래시는 의도적으로 만든 `EXCEPTION_ACCESS_VIOLATION (0xC0000005)`입니다.
원인은 널 포인터에 대한 쓰기(`write to null pointer`)입니다.

분석 시 기대되는 핵심 정보:

- 예외 코드: `0xC0000005`
- 예외 이름: `EXCEPTION_ACCESS_VIOLATION`
- 주요 함수: `` `anonymous namespace'::TriggerAccessViolation ``
- 소스 파일: `main.cpp` (PDB 원본 경로 정보에 따라 분석 결과에 `src/main.cpp`로 표시될 수 있음)

## MCP 테스트 용도

이 샘플은 다음 흐름을 검증하는 데 사용합니다.

- `register_dump`
- `analyze_dump`
- `get_source_context`

즉, AI Agent가 덤프에서 크래시 지점을 찾고, 해당 소스 라인을 바탕으로 수정 제안을 생성하는 시나리오를 검증하기 위한 데이터셋입니다.
