from windows_dump_analysis_mcp.errors import ErrorCode, ServerError


def test_error_serialization_shape() -> None:
    payload = ServerError(
        ErrorCode.INVALID_REQUEST,
        "Bad input",
        {"field": "dump_path"},
    ).to_dict()

    assert payload["ok"] is False
    assert payload["error"]["code"] == ErrorCode.INVALID_REQUEST
    assert payload["error"]["message"] == "Bad input"
    assert payload["error"]["details"]["field"] == "dump_path"
