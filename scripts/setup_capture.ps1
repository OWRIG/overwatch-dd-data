<#
.SYNOPSIS
  搭建/还原 mitmproxy 抓包环境，用于识别本人网易DD datamsapi 会话参数。
.USAGE
  .\setup_capture.ps1                         启动监听，自动保存并临时接管系统代理
  .\setup_capture.ps1 -UpstreamProxy 127.0.0.1:7897
                                               监听 8080，并把流量转发到已有代理
  .\setup_capture.ps1 -Cleanup                 停监听并恢复原代理设置
  .\setup_capture.ps1 -Check                   检查当前状态
.DISCLAIMER
  仅供本人账号、本机、本地分析使用。抓完务必 -Cleanup。
#>
param(
  [switch]$Cleanup,
  [switch]$Check,
  [string]$UpstreamProxy,
  [switch]$SkipCAInstall,
  [switch]$KeepCA,
  [int]$Port = 8080
)

$PORT = $Port
$ADDON = "$PSScriptRoot\ow_capture_addon.py"
$CA_DIR = "$env:USERPROFILE\.mitmproxy"
$REG = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
$STATE_FILE = "$PSScriptRoot\capture_state.json"

function Get-CAThumb {
  $c = Get-ChildItem Cert:\CurrentUser\Root -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -match 'mitmproxy' } |
    Select-Object -First 1
  if ($c) { $c.Thumbprint }
}

function Get-ProxyState {
  $p = Get-ItemProperty -Path $REG -Name ProxyEnable,ProxyServer,ProxyOverride -ErrorAction SilentlyContinue
  [pscustomobject]@{
    ProxyEnable   = if ($null -ne $p.ProxyEnable) { [int]$p.ProxyEnable } else { 0 }
    ProxyServer   = if ($null -ne $p.ProxyServer) { [string]$p.ProxyServer } else { "" }
    ProxyOverride = if ($null -ne $p.ProxyOverride) { [string]$p.ProxyOverride } else { "" }
  }
}

function Save-State {
  param([string]$ResolvedUpstream)
  $proxy = Get-ProxyState
  [pscustomobject]@{
    proxyEnable   = $proxy.ProxyEnable
    proxyServer   = $proxy.ProxyServer
    proxyOverride = $proxy.ProxyOverride
    caThumbBefore = "$(Get-CAThumb)"
    upstreamProxy = $ResolvedUpstream
    savedAt       = (Get-Date).ToString("s")
  } | ConvertTo-Json | Set-Content -Path $STATE_FILE -Encoding UTF8
}

function Restore-Proxy {
  if (Test-Path $STATE_FILE) {
    $s = Get-Content -Raw -Encoding UTF8 $STATE_FILE | ConvertFrom-Json
    Set-ItemProperty -Path $REG -Name ProxyEnable -Value ([int]$s.proxyEnable) -ErrorAction SilentlyContinue
    if ($s.proxyServer) {
      Set-ItemProperty -Path $REG -Name ProxyServer -Value ([string]$s.proxyServer) -ErrorAction SilentlyContinue
    }
    if ($s.proxyOverride) {
      Set-ItemProperty -Path $REG -Name ProxyOverride -Value ([string]$s.proxyOverride) -ErrorAction SilentlyContinue
    }
    return $s
  }
  Set-ItemProperty -Path $REG -Name ProxyEnable -Value 0 -ErrorAction SilentlyContinue
  return $null
}

function Get-MitmdumpPath {
  $cmd = Get-Command mitmdump -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $fallback = "C:\Program Files\mitmproxy\bin\mitmdump.exe"
  if (Test-Path $fallback) { return $fallback }
  return $null
}

function Ensure-Mitmdump {
  $exe = Get-MitmdumpPath
  if ($exe) { return $exe }
  Write-Output "Installing mitmproxy..."
  winget install --id mitmproxy.mitmproxy -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Null
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
  $exe = Get-MitmdumpPath
  if (-not $exe) { throw "mitmdump not found" }
  return $exe
}

function Ensure-CAFile {
  param([string]$Exe)
  if (Test-Path "$CA_DIR\mitmproxy-ca-cert.cer") { return }
  $p = Start-Process -FilePath $Exe -ArgumentList '-p',$PORT,'--set','listen_host=127.0.0.1' -PassThru -WindowStyle Hidden
  Start-Sleep 5
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}

function Try-InstallCA {
  if ($SkipCAInstall) { return }
  if (Get-CAThumb) { return }
  $cert = "$CA_DIR\mitmproxy-ca-cert.cer"
  if (-not (Test-Path $cert)) { return }
  Write-Output "Installing mitmproxy CA to CurrentUser Root..."
  $p = Start-Process -FilePath "certutil.exe" -ArgumentList '-user','-addstore','-f','Root',$cert -PassThru -WindowStyle Hidden
  $done = Wait-Process -Id $p.Id -Timeout 20 -ErrorAction SilentlyContinue
  if (-not $done -and -not $p.HasExited) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    Write-Output "CA import needs manual confirmation. Open this file and install it to CurrentUser\\Trusted Root Certification Authorities:"
    Write-Output "  $cert"
    Write-Output "Then rerun: .\setup_capture.ps1"
    return
  }
  Write-Output "CA cert: $(if(Get-CAThumb){Get-CAThumb}else{'not installed'})"
}

if ($Check) {
  $mp = Get-MitmdumpPath
  $listen = Get-NetTCPConnection -State Listen -LocalPort $PORT -ErrorAction SilentlyContinue
  $proxy = Get-ProxyState
  $ca = Get-CAThumb
  Write-Output "mitmdump: $(if($mp){'installed'}else{'NOT installed'})"
  Write-Output "listen : $(if($listen){'active on '+$PORT}else{'no'})"
  Write-Output "proxy  : $(if($proxy.ProxyEnable -eq 1){'ENABLED '+$proxy.ProxyServer}else{'disabled'})"
  Write-Output "CA cert: $(if($ca){$ca}else{'not installed'})"
  Write-Output "state  : $(if(Test-Path $STATE_FILE){$STATE_FILE}else{'none'})"
  return
}

if ($Cleanup) {
  Get-Process mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  $state = Restore-Proxy
  $ca = Get-CAThumb
  if ($ca -and -not $KeepCA) {
    $hadBefore = $state -and $state.caThumbBefore
    if (-not $hadBefore) {
      $p = Start-Process -FilePath "certutil.exe" -ArgumentList '-user','-delstore','Root',$ca -PassThru -WindowStyle Hidden
      Wait-Process -Id $p.Id -Timeout 15 -ErrorAction SilentlyContinue | Out-Null
      if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
  }
  Remove-Item $STATE_FILE -Force -ErrorAction SilentlyContinue
  Write-Output "Cleanup done: mitmdump stopped, proxy restored, temporary CA removed if this script installed it."
  return
}

$exe = Ensure-Mitmdump
Ensure-CAFile -Exe $exe
Try-InstallCA

$oldProxy = Get-ProxyState
$resolvedUpstream = $UpstreamProxy
if (-not $resolvedUpstream -and $oldProxy.ProxyEnable -eq 1 -and $oldProxy.ProxyServer -and $oldProxy.ProxyServer -ne "127.0.0.1:$PORT") {
  $resolvedUpstream = $oldProxy.ProxyServer
}

Save-State -ResolvedUpstream $resolvedUpstream

Get-Process mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$args = @('-p', "$PORT", '--set', 'listen_host=127.0.0.1', '--set', 'flow_detail=0', '-s', $ADDON)
if ($resolvedUpstream) {
  $up = $resolvedUpstream
  if ($up -notmatch '^[a-zA-Z]+://') { $up = "http://$up" }
  $args = @('-p', "$PORT", '--set', 'listen_host=127.0.0.1', '--set', 'flow_detail=0', '--mode', "upstream:$up", '-s', $ADDON)
  Write-Output "Using upstream proxy: $up"
}

Set-ItemProperty -Path $REG -Name ProxyEnable -Value 1
Set-ItemProperty -Path $REG -Name ProxyServer -Value "127.0.0.1:$PORT"
Set-ItemProperty -Path $REG -Name ProxyOverride -Value "<local>"
Write-Output "Proxy set to 127.0.0.1:$PORT"

$p = Start-Process -FilePath $exe -ArgumentList $args -WindowStyle Hidden -PassThru
Start-Sleep 2
$listen = Get-NetTCPConnection -State Listen -LocalPort $PORT -ErrorAction SilentlyContinue
Write-Output "mitmdump pid=$($p.Id) listen=$(if($listen){'yes'}else{'no'})"
Write-Output ">>> 完全退出并重开网易DD -> 登录 -> 进入守望先锋战绩/统计页 -> 切换快速/赛季/英雄/地图"
Write-Output ">>> 看到 scripts\creds.json 生成后运行: .\setup_capture.ps1 -Cleanup"
