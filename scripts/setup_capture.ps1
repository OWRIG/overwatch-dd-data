<#
.SYNOPSIS
  一键搭建/还原 mitmproxy 抓包环境，用于抓取网易DD的 datamsapi token
.USAGE
  .\setup_capture.ps1            搭建环境（装mitmproxy+CA+代理+启动监听）
  .\setup_capture.ps1 -Cleanup   还原（停监听+删CA+关代理）
  .\setup_capture.ps1 -Check     检查当前状态
.DISCLAIMER
  仅供学习交流使用，不得用于商业用途。使用者需遵守网易DD及暴雪服务条款，自负风险。
  抓完务必 -Cleanup 还原系统，勿长期挂代理给服务造成压力。
#>
param([switch]$Cleanup,[switch]$Check)

$PORT=8080
$ADDON="$PSScriptRoot\ow_capture_addon.py"
$CA_DIR="$env:USERPROFILE\.mitmproxy"
$REG="HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

function Get-CAThumb{
  $c=Get-ChildItem Cert:\CurrentUser\Root -ErrorAction SilentlyContinue | Where-Object { $_.Subject -match 'mitmproxy' }
  if($c){$c.Thumbprint}
}

if($Check){
  $mp=Get-Command mitmdump -ErrorAction SilentlyContinue
  $listen=Get-NetTCPConnection -State Listen -LocalPort $PORT -ErrorAction SilentlyContinue
  $proxy=(Get-ItemProperty -Path $REG -Name ProxyEnable -ErrorAction SilentlyContinue).ProxyEnable
  $ca=Get-CAThumb
  Write-Output "mitmdump: $(if($mp){'installed'}else{'NOT installed'})"
  Write-Output "listen : $(if($listen){'active on '+$PORT}else{'no'})"
  Write-Output "proxy  : $(if($proxy -eq 1){'ENABLED'}else{'disabled'})"
  Write-Output "CA cert: $(if($ca){$ca}else{'not installed'})"
  return
}

if($Cleanup){
  Get-Process mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Set-ItemProperty -Path $REG -Name ProxyEnable -Value 0 -ErrorAction SilentlyContinue
  $ca=Get-CAThumb
  if($ca){ & certutil -user -delstore Root $ca 2>$null | Out-Null }
  Write-Output "Cleanup done: mitmdump stopped, proxy disabled, CA removed (if any)"
  return
}

# 搭建
$mp=Get-Command mitmdump -ErrorAction SilentlyContinue
if(-not $mp){
  Write-Output "Installing mitmproxy..."
  winget install --id mitmproxy.mitmproxy -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Null
  $env:Path=[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')
}
$exe=(Get-Command mitmdump -ErrorAction SilentlyContinue).Source
if(-not $exe){ $exe="C:\Program Files\mitmproxy\bin\mitmdump.exe" }
if(-not (Test-Path $exe)){ Write-Error "mitmdump not found"; return }

# 生成CA（首次启动）
if(-not (Test-Path "$CA_DIR\mitmproxy-ca-cert.cer")){
  $p=Start-Process -FilePath $exe -ArgumentList '-p',"",$PORT,'--set','listen_host=127.0.0.1' -PassThru -WindowStyle Hidden
  Start-Sleep 5; Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}

# 装CA证书
if(-not (Get-CAThumb)){
  & certutil -user -addstore -f Root "$CA_DIR\mitmproxy-ca-cert.cer" 2>$null | Out-Null
  Write-Output "CA installed: $(Get-CAThumb)"
}

# 设代理
Set-ItemProperty -Path $REG -Name ProxyEnable -Value 1
Set-ItemProperty -Path $REG -Name ProxyServer -Value "127.0.0.1:$PORT"
Set-ItemProperty -Path $REG -Name ProxyOverride -Value "<local>"
Write-Output "Proxy set to 127.0.0.1:$PORT"

# 启动mitmdump（带addon）
Write-Output "Starting mitmdump with capture addon..."
Write-Output ">>> 现在请: 完全退出并重开网易DD -> 登录 -> 进入守望先锋战绩/统计页 -> 切换英雄/地图/赛季"
Write-Output ">>> 看到 'CREDS CAPTURED' 即抓到token, 写入 scripts\creds.json"
Write-Output ">>> 抓完后运行: .\setup_capture.ps1 -Cleanup"
Start-Process -FilePath $exe -ArgumentList '-p',"",$PORT,'--set','listen_host=127.0.0.1','--set','flow_detail=0','-s',$ADDON -WindowStyle Normal
