<#
  setup-runner-autostart.ps1
  -----------------------------------------------------------------------------
  Faz o self-hosted runner do GitHub Actions subir SOZINHO no boot da máquina
  (sem ninguém precisar logar ou abrir terminal), para a coleta de licitações
  rodar de forma autônoma.

  POR QUÊ ISSO EXISTE: o portal de Curitiba (consultalicitacao.curitiba.pr.gov.br:9090)
  recusa conexões de datacenters fora da rede aceita (GitHub-hosted, Render, etc.) —
  confirmado pelo probe. E a coleta exige navegador real (Playwright). Então o único
  coletor viável com a stack do projeto é um runner self-hosted numa rede BR aceita.
  Este script torna esse runner "set-and-forget".

  O QUE FAZ: cria uma Tarefa Agendada que executa run.cmd como SYSTEM, no startup,
  reiniciando se cair. Não precisa de token nem reconfigurar o runner.

  COMO USAR (uma vez, na máquina coletora):
    Clique direito neste arquivo > "Executar com o PowerShell"  (aceite o UAC)
    — ou —
    powershell -ExecutionPolicy Bypass -File scripts\setup-runner-autostart.ps1

  Para remover:  Unregister-ScheduledTask -TaskName "GitHubRunner-AgroIA" -Confirm:$false
#>
param(
  [string]$RunnerPath = "C:\Users\hvcam\actions-runner",
  [string]$TaskName   = "GitHubRunner-AgroIA"
)

# Auto-elevação para Administrador (necessário p/ tarefa AtStartup como SYSTEM).
$ident = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $ident.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    Write-Host "Elevando para Administrador..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`"",
        "-RunnerPath","`"$RunnerPath`"","-TaskName","`"$TaskName`""
    )
    exit
}

$runCmd = Join-Path $RunnerPath "run.cmd"
if (-not (Test-Path $runCmd)) {
    Write-Error "run.cmd nao encontrado em '$RunnerPath'. Ajuste -RunnerPath para a pasta do runner."
    exit 1
}

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runCmd`"" -WorkingDirectory $RunnerPath
$trigger = New-ScheduledTaskTrigger -AtStartup
# SYSTEM/ServiceAccount: roda no boot sem login e sem senha.
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "OK: tarefa '$TaskName' criada e iniciada."
Write-Host "    O runner sobe automaticamente no boot (sem login) e reinicia se cair."
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table -AutoSize
