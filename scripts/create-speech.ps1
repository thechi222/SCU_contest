$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$relayRoot = Split-Path -Parent $PSScriptRoot
$relayOutput = Join-Path $relayRoot 'demo-assets'
New-Item -ItemType Directory -Force -Path $relayOutput | Out-Null
$relaySynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $relayVoice = $relaySynth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'zh-TW' } | Select-Object -First 1
    if ($relayVoice) {
        $relaySynth.SelectVoice($relayVoice.VoiceInfo.Name)
        $relaySpeech = '歡迎來到算力接力站。我們讓校園裡閒置的顯示卡，幫同學完成語音轉文字與圖片放大。設備主人隨時可以停止共享，未完成的工作會重新排隊。'
    } else {
        $relaySpeech = 'Welcome to Campus Compute Relay. We share idle graphics cards to help students transcribe audio and enlarge images. Device owners can stop sharing at any time. Unfinished jobs return to the queue.'
    }
    $relaySynth.SetOutputToWaveFile((Join-Path $relayOutput 'introduction.wav'))
    $relaySynth.Speak($relaySpeech)
    Set-Content -LiteralPath (Join-Path $relayOutput 'introduction-reference.txt') -Value $relaySpeech -Encoding UTF8
} finally { $relaySynth.Dispose() }
Write-Output 'Created offline synthetic speech and reference text in demo-assets/'
