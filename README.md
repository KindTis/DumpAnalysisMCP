# DumpAnalysisMCP

DumpAnalysisMCP는 Windows 크래시 덤프(minidump/full dump)를 분석하는 MCP(Model Context Protocol) 서버입니다.  
MCP 클라이언트가 `stdio` 기반으로 덤프 분석, 스레드 조회, 소스 문맥 조회, 안전한 패치/빌드/테스트를 호출할 수 있도록 설계되었습니다.

## 프로젝트 소개

- 목적: AI Agent가 Windows dump를 구조화된 데이터로 읽고 원인 분석 속도를 높이도록 지원
- 대상: user-mode C++/Unreal Engine 덤프 분석
- 핵심 강점:
  - 예외/스택/모듈/심볼 품질 구조화
  - 멀티스레드 분석(`threads`, `crashing_thread`, `faulting_thread_confidence`)
  - `source_path_map` 기반 소스 경로 remap
  - 정책 기반 안전 실행(`apply_patch`, `build_project`, `run_tests`)

## 주요 기능

- dump 세션 등록 및 `dump_id` 발급
- `analyze_dump` 정규화 결과 제공
- 스레드 목록/스레드별 스택 조회
- 예외/모듈/경고 리소스 조회
- 소스 문맥 조회 및 코드 참조 검색
- 확인 플래그 기반의 안전한 파일 변경/빌드/테스트 실행

## 요구 사항

- OS: Windows 10/11
- Python: 3.11 이상
- 디버거: WinDbg 또는 Debugging Tools for Windows (`cdb.exe`)
- 입력 경로:
  - `dump_path`: 존재하는 dump 파일(절대 경로)
  - `symbol_root`: 존재하는 디렉터리(절대 경로)
  - `source_root`: 존재하는 디렉터리(절대 경로)
- `project_type`: `native_cpp` 또는 `unreal_engine`

환경 변수(선택):

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `DUMP_MCP_CDB_PATH` | `cdb.exe` | `cdb.exe` 경로. 환경 차이를 줄이려면 절대 경로 권장 |
| `DUMP_MCP_LOG_LEVEL` | `WARNING` | 로그 레벨 |
| `DUMP_MCP_ANALYZE_TIMEOUT_SECONDS` | `180` | dump 분석 타임아웃 |
| `DUMP_MCP_BUILD_TIMEOUT_SECONDS` | `1200` | 빌드 타임아웃 |
| `DUMP_MCP_TEST_TIMEOUT_SECONDS` | `1800` | 테스트 타임아웃 |
| `DUMP_MCP_MAX_OUTPUT_CHARS` | `200000` | stdout/stderr 최대 보존 길이 |
| `DUMP_MCP_BUILD_ALLOWLIST` | `msbuild,dotnet,cmake,ninja,UnrealBuildTool,RunUAT` | 빌드 허용 실행 파일 |
| `DUMP_MCP_TEST_ALLOWLIST` | `ctest,dotnet,pytest,UnrealEditor-Cmd,RunUAT` | 테스트 허용 실행 파일 |

## 설치

기본 설치:

```powershell
python -m pip install -e .
```

개발 설치(테스트 포함):

```powershell
python -m pip install -e .[dev]
```

## 빠른 시작

1. `cdb.exe` 경로 설정(예시)

```powershell
$env:DUMP_MCP_CDB_PATH="C:\Program Files\WindowsApps\Microsoft.WinDbg_1.2601.12001.0_x64__8wekyb3d8bbwe\amd64\cdb.exe"
$env:DUMP_MCP_LOG_LEVEL="INFO"
```

2. MCP 클라이언트 설정(`.vscode/mcp.json` 등)

`servers` 형식:

```json
{
  "servers": {
    "dump-analysis": {
      "command": "python",
      "args": ["-m", "windows_dump_analysis_mcp"],
      "env": {
        "DUMP_MCP_CDB_PATH": "<REPLACE_WITH_CDB_ABSOLUTE_PATH>",
        "DUMP_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```


`mcpServers` 형식:

```json
{
  "mcpServers": {
    "dump-analysis": {
      "command": "python",
      "args": ["-m", "windows_dump_analysis_mcp"],
      "env": {
        "DUMP_MCP_CDB_PATH": "<REPLACE_WITH_CDB_ABSOLUTE_PATH>",
        "DUMP_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## 사용법

기본 분석 흐름:

1. `register_dump`
2. `analyze_dump`
3. 필요 시 `get_thread_list`, `get_thread_stack_trace`, `get_source_context`

`register_dump` 예시 payload:

```json
{
  "dump_path": "C:\\path\\to\\sample.dmp",
  "symbol_root": "C:\\path\\to\\symbols",
  "source_root": "C:\\path\\to\\source",
  "project_type": "native_cpp",
  "binary_root": "C:\\path\\to\\bin",
  "source_path_map": {
    "c:\\original\\source\\root": "C:\\path\\to\\source"
  }
}
```

## Tool 레퍼런스

| Tool | 설명 | 주요 인자 |
|---|---|---|
| `register_dump` | 분석 세션 등록 후 `dump_id` 반환 | `dump_path`, `symbol_root`, `source_root`, `project_type`, `binary_root?`, `dump_type_hint?`, `log_paths?`, `source_path_map?` |
| `analyze_dump` | dump 분석 실행 및 정규화 결과 반환 | `dump_id` |
| `get_exception_info` | 예외 요약 조회 | `dump_id` |
| `get_stack_trace` | 선택 스레드 스택 조회(기본: crashing thread) | `dump_id`, `max_frames?`, `thread_id?` |
| `get_thread_list` | 스레드 목록/충돌 메타데이터 조회 | `dump_id` |
| `get_thread_stack_trace` | 특정 스레드 스택 조회 | `dump_id`, `thread_id`, `max_frames?` |
| `get_module_list` | 모듈 목록/심볼 품질 조회 | `dump_id` |
| `get_source_context` | 선택 프레임/스레드 소스 문맥 조회 | `dump_id`, `frame_index?`, `context_before?`, `context_after?`, `thread_id?` |
| `search_code_references` | 코드 참조 검색 | `query`, `dump_id?`, `source_root?`, `max_results?`, `ignore_case?` |
| `apply_patch` | 파일 변경 preview/apply | `changes`, `dump_id?`, `source_root?`, `mode?`, `user_confirmed?` |
| `build_project` | 가드된 빌드 실행 | `command`, `dump_id?`, `working_directory?`, `timeout_seconds?`, `user_confirmed=true` |
| `run_tests` | 가드된 테스트 실행 | `command`, `dump_id?`, `working_directory?`, `timeout_seconds?`, `user_confirmed=true` |

## Resource 레퍼런스

- `project://symbols/status`
- `project://source/root`
- `crash://{dump_id}/summary`
- `crash://{dump_id}/exception`
- `crash://{dump_id}/stack`
- `crash://{dump_id}/threads`
- `crash://{dump_id}/modules`
- `crash://{dump_id}/warnings`
- `crash://{dump_id}/source/main-frame`

## 안전 정책

- `build_project`, `run_tests`: `user_confirmed=true` 필수
- `apply_patch`:
  - 기본은 `preview`
  - `mode=apply`는 `user_confirmed=true` 필수
- 빌드/테스트 명령은 allowlist 실행 파일만 허용
- 쉘 체이닝(`&&`, `|`, `;`) 차단

## 예제

- `examples/cpp-crash-sample-1`
- `examples/cpp-crash-sample-2`
- `examples/cpp-crash-sample-3`

## 개발

테스트 실행:

```powershell
python -m pytest -q
```

## 트러블슈팅

- `Configured cdb_path must be an absolute path`:
  - `DUMP_MCP_CDB_PATH`를 절대 경로로 설정하세요.
- `source_root does not exist` 또는 source mapping 오류:
  - `source_root` 절대 경로와 `source_path_map` 매핑을 확인하세요.
- 심볼 품질이 낮거나 `WRONG_SYMBOLS` 경고가 보이는 경우:
  - `symbol_root`에 올바른 PDB가 있는지 확인하세요.
