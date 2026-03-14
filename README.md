# DumpAnalysisMCP

DumpAnalysisMCP는 Windows 환경에서 minidump/full dump를 분석하기 위한 MCP(Model Context Protocol) 서버입니다.  
서버는 `stdio` 전송을 사용하며, MCP 클라이언트가 dump 분석/소스 문맥 조회/패치/빌드/테스트를 안전하게 호출할 수 있도록 설계되었습니다.

## 기능 설명
- dump 세션 등록: dump/symbol/source 경로를 검증하고 `dump_id`를 발급합니다.
- 충돌 분석: WinDbg 계열 `cdb.exe`를 사용해 예외 코드, 스택, 모듈, 심볼 상태를 구조화합니다.
- 소스 연계 분석: 스택 프레임 기준 코드 문맥 조회와 코드 참조 검색을 제공합니다.
- 안전한 변경/검증: `apply_patch`, `build_project`, `run_tests`에 확인 플래그와 정책 가드를 적용합니다.
- MCP 리소스 제공: `project://...`, `crash://...` URI로 분석 결과를 읽을 수 있습니다.

## 요구 사항
- OS: Windows 10/11
- Python: 3.11 이상
- 디버거: WinDbg(또는 Debugging Tools for Windows)의 `cdb.exe`
- 경로 준비:
  - `dump_path`: 존재하는 dump 파일
  - `symbol_root`: 존재하는 심볼 디렉터리
  - `source_root`: 존재하는 소스 루트 디렉터리
- `project_type`: `native_cpp` 또는 `unreal_engine`

환경 변수(선택/기본값):

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `DUMP_MCP_CDB_PATH` | `cdb.exe` | `cdb.exe` 절대 경로 (권장) |
| `DUMP_MCP_LOG_LEVEL` | `WARNING` | 로그 레벨 |
| `DUMP_MCP_ANALYZE_TIMEOUT_SECONDS` | `180` | dump 분석 타임아웃 |
| `DUMP_MCP_BUILD_TIMEOUT_SECONDS` | `1200` | 빌드 타임아웃 |
| `DUMP_MCP_TEST_TIMEOUT_SECONDS` | `1800` | 테스트 타임아웃 |
| `DUMP_MCP_MAX_OUTPUT_CHARS` | `200000` | stdout/stderr 최대 보존 길이 |
| `DUMP_MCP_BUILD_ALLOWLIST` | `msbuild,dotnet,cmake,ninja,UnrealBuildTool,RunUAT` | 빌드 허용 실행 파일 |
| `DUMP_MCP_TEST_ALLOWLIST` | `ctest,dotnet,pytest,UnrealEditor-Cmd,RunUAT` | 테스트 허용 실행 파일 |

## 설치
1. 의존성 설치

```powershell
python -m pip install -e .
```

개발용(테스트 포함):

```powershell
python -m pip install -e .[dev]
```

2. 환경 변수 설정(예시)

```powershell
$env:DUMP_MCP_CDB_PATH="C:\Program Files\WindowsApps\Microsoft.WinDbg_1.2601.12001.0_x64__8wekyb3d8bbwe\amd64\cdb.exe"
$env:DUMP_MCP_LOG_LEVEL="INFO"
```

3. 서버 실행

```powershell
python -m windows_dump_analysis_mcp
```

## MCP 클라이언트 추가를 위한 JSON 설정
아래 예시는 워크스페이스 `.vscode/mcp.json` 또는 클라이언트 설정 파일에 적용할 수 있는 형태입니다.  
(클라이언트에 따라 루트 키가 `servers` 또는 `mcpServers`일 수 있습니다.)

`servers` 형식 예시:

```json
{
  "servers": {
    "dump-analysis": {
      "command": "python",
      "args": [
        "-m",
        "windows_dump_analysis_mcp"
      ],
      "env": {
        "DUMP_MCP_CDB_PATH": "cdb.exe",
        "DUMP_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

`mcpServers` 형식 예시:

```json
{
  "mcpServers": {
    "dump-analysis": {
      "command": "python",
      "args": [
        "-m",
        "windows_dump_analysis_mcp"
      ],
      "env": {
        "DUMP_MCP_CDB_PATH": "cdb.exe",
        "DUMP_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## MCP 명령어 세트 설명
### Tools

| 명령어 | 설명 | 주요 인자 |
|---|---|---|
| `register_dump` | 분석 세션 등록 후 `dump_id` 반환 | `dump_path`, `symbol_root`, `source_root`, `project_type`, `binary_root?`, `dump_type_hint?`, `log_paths?` |
| `analyze_dump` | 등록된 dump 전체 분석 수행 | `dump_id` |
| `get_exception_info` | 예외 코드/이름/유형/주소 조회 | `dump_id` |
| `get_stack_trace` | 스택 프레임 조회 | `dump_id`, `max_frames?`, `thread_id?` |
| `get_module_list` | 로드 모듈 및 심볼 품질 조회 | `dump_id` |
| `get_source_context` | 특정 프레임 주변 소스 문맥 조회 | `dump_id`, `frame_index?`, `context_before?`, `context_after?` |
| `search_code_references` | 코드 참조 검색 | `query`, `dump_id?` 또는 `source_root?`, `max_results?`, `ignore_case?` |
| `apply_patch` | 파일 변경 미리보기/적용 | `changes`, `dump_id?` 또는 `source_root?`, `mode=preview/apply`, `user_confirmed?` |
| `build_project` | 정책 기반 빌드 실행 | `command`, `dump_id?`, `working_directory?`, `timeout_seconds?`, `user_confirmed` |
| `run_tests` | 정책 기반 테스트 실행 | `command`, `dump_id?`, `working_directory?`, `timeout_seconds?`, `user_confirmed` |

정책/가드 요약:
- `build_project`, `run_tests`는 `user_confirmed=true`가 필수입니다.
- 빌드/테스트 명령은 allowlist 실행 파일만 허용됩니다.
- `&&`, `|`, `;` 같은 쉘 체이닝 연산자는 차단됩니다.
- `apply_patch`는 기본 `preview` 모드이며, `apply` 모드는 `user_confirmed=true`가 필요합니다.

### Resources
- `project://symbols/status`
- `project://source/root`
- `crash://{dump_id}/summary`
- `crash://{dump_id}/exception`
- `crash://{dump_id}/stack`
- `crash://{dump_id}/modules`
- `crash://{dump_id}/warnings`
- `crash://{dump_id}/source/main-frame`
