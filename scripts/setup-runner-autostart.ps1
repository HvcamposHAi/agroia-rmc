<#
  setup-runner-autostart.ps1
  -----------------------------------------------------------------------------
  Faz o self-hosted runner do GitHub Actions subir SOZINHO quando o usuário faz
  logon no Windows, para a coleta diária de licitações (coleta.yml) rodar sem
  ninguém abrir terminal.

  POR QUÊ EXISTE: os portais da Prefeitura de Curitiba recusam IPs de datacenter
  (GitHub-hosted, Render...) — confirmado de novo em 24/09/2026 com o Portal da
  Transparência. A coleta só funciona a partir de uma rede BR aceita (este PC).

  POR QUÊ NO LOGON DO USUÁRIO (e não SYSTEM no boot): as credenciais do runner
  (.credentials_rsaparams) são cifradas com DPAPI na conta de quem configurou o
  runner; rodando como SYSTEM ele pode não conseguir decifrá-las. Tarefa do próprio
  usuário também dispensa privilégio de administrador.
  Se o PC estiver desligado às 06:00, o job agendado espera na fila do GitHub (até
  24 h) e roda assim que o runner voltar.

  COMO USAR (uma vez):
    powershell -ExecutionPolicy Bypass -File scripts\setup-runner-autostart.ps1

  Para remover:  Unregister-ScheduledTask -TaskName "GitHubRunner-AgroIA" -Confirm:$false
#>
param(
  [string]$RunnerPath = "C:\Users\hvcam\actions-runner",
  [string]$TaskName   = "GitHubRunner-AgroIA"
)

$runCmd = Join-Path $RunnerPath "run.cmd"
if (-not (Test-Path $runCmd)) {
    Write-Error "run.cmd nao encontrado em '$RunnerPath'. Ajuste -RunnerPath para a pasta do runner."
    exit 1
}

$usuario  = "$env:USERDOMAIN\$env:USERNAME"
$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runCmd`"" -WorkingDirectory $RunnerPath
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "OK: tarefa '$TaskName' criada para $usuario (inicia o runner no logon)."
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table -AutoSize
