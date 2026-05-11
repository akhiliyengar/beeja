# builder post-session-hook (Windows / PowerShell port).
#
# Append a signal record after every chat session that invoked the builder.
# Functionally equivalent to post-session-hook.sh; use this on Windows where
# bash + jq are not available.
#
# Receives a JSON blob on stdin describing the session:
#   { "session_id": "...", "tool_calls": [...], "duration_ms": ..., ... }
#
# Writes one JSONL record per builder-touching session to:
#   $env:AGENTS_SHADOW_ROOT\_signals\builder.jsonl
#
# Wire into VS Code via "chat.hooks.enabled": true and a hook entry pointing
# here, e.g.:
#   "chat.hooks.postSession":
#     "powershell -NoProfile -ExecutionPolicy Bypass -File ${workspaceFolder}/integrations/vscode_config/post-session-hook.ps1"

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$shadowRoot  = if ($env:AGENTS_SHADOW_ROOT) { $env:AGENTS_SHADOW_ROOT } else { Join-Path $HOME 'agents\shadow' }
$signalsDir  = Join-Path $shadowRoot '_signals'
$signalsFile = Join-Path $signalsDir 'builder.jsonl'

New-Item -ItemType Directory -Force -Path $signalsDir | Out-Null

$payloadText = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($payloadText)) { exit 0 }

try {
    $payload = $payloadText | ConvertFrom-Json
} catch {
    Write-Error "post-session-hook: stdin was not valid JSON: $_"
    exit 1
}

$toolCalls = @($payload.tool_calls)
$builderTouched = $false
foreach ($c in $toolCalls) {
    if ($c.name -in @('build_artifact', 'revise_artifact')) { $builderTouched = $true; break }
}
if (-not $builderTouched) { exit 0 }

$drafts = 0
$revisions = 0
foreach ($c in $toolCalls) {
    if ($c.name -eq 'build_artifact' -and $c.result.status -eq 'complete') { $drafts++ }
    if ($c.name -eq 'revise_artifact')                                     { $revisions++ }
}

$record = [ordered]@{
    ts                  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    session_id          = $payload.session_id
    duration_ms         = $payload.duration_ms
    tool_calls          = @($toolCalls | ForEach-Object { $_.name })
    drafts_written      = $drafts
    revisions           = $revisions
    user_marked_quality = $payload.user_feedback.rating
}

# Append as one JSON object per line. Use raw UTF-8 (no BOM) so downstream
# JSONL readers don't see U+FEFF on the first line.
$line = ($record | ConvertTo-Json -Compress -Depth 6) + "`n"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::AppendAllText($signalsFile, $line, $utf8NoBom)
