# Verification report

## Checks performed

- ZIP archive integrity: PASS (verified with Python zipfile testzip).
- Required project files: PASS.
- Python syntax compilation: PASS.
- Backend automated tests: PASS ([32m[32m[1m8 passed[0m[32m in 0.07s[0m[0m).
- Frontend dependency installation/build: NOT VERIFIED. `npm install` did not finish within the available verification window.
- Docker build/run: NOT VERIFIED. Docker is not installed in this verification environment.
- Public deployment: NOT DONE.

## Exact backend test output

```text
[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                                                                 [100%][0m
[32m[32m[1m8 passed[0m[32m in 0.07s[0m[0m

Spreadsheet runtime warmup failed during python startup
Traceback (most recent call last):
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/patches/warm_spreadsheet_runtime_on_startup.py", line 26, in warm_spreadsheet_runtime_on_startup
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/spreadsheet_warmup.py", line 785, in warm_spreadsheet_runtime
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/spreadsheet_warmup.py", line 718, in _warm_feature_flows
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/spreadsheet_warmup.py", line 509, in _warm_drawing_and_image_flows
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/generated/interface/models.py", line 32861, in bring_to_front
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/rpc/remote.py", line 764, in __call__
  File "/tmp/tmp.QlpUkOUI9D/artifact_tool_v2-2.8.66/artifact_tool/rpc/client.py", line 175, in call
artifact_tool.rpc.client.RemoteError: Element ordering requires an owning element collection.

```

## Required files missing
- None

## Important limitations
This is a deterministic, synthetic-data analytics MVP. It is not yet an LLM-powered multi-agent Text-to-SQL system and is not production hardened. Do not connect it to sensitive production databases. The SQL guard is a demo defense-in-depth layer, not a formally secure SQL sandbox.
