@echo off
REM Remove os desktop.ini que o Google Drive cria DENTRO da pasta .git
REM
REM Rode quando o Git reclamar com mensagens como:
REM   fatal: bad object refs/desktop.ini
REM   error: unable to write reflog
REM   fatal: failed to run repack
REM
REM Nao apaga nada do seu codigo nem do historico: desktop.ini e apenas
REM um arquivo de icone do Windows, nao faz parte do Git.

cd /d "%~dp0"

if not exist .git (
    echo ERRO: pasta .git nao encontrada aqui.
    pause
    exit /b 1
)

echo.
echo Limpando desktop.ini de dentro do .git ...
echo.

powershell -NoProfile -Command ^
  "$f = Get-ChildItem -Path '.git' -Recurse -Force -Filter 'desktop.ini' -ErrorAction SilentlyContinue;" ^
  "$ok = 0; $fail = 0;" ^
  "foreach ($x in $f) { try { Remove-Item $x.FullName -Force -ErrorAction Stop; $ok++ } catch { $fail++ } };" ^
  "Write-Host ''; Write-Host ('  removidos: ' + $ok + '   nao removidos: ' + $fail);" ^
  "if ($fail -gt 0) { Write-Host '  (pause a sincronizacao do Drive e rode de novo)' }"

echo.
echo Verificando o repositorio...
echo.
git status --short >nul 2>&1
if errorlevel 1 (
    echo   ATENCAO: o git ainda reporta erro. Pause a sincronizacao do
    echo   Google Drive pelo icone na barra de tarefas e rode novamente.
) else (
    echo   OK: o repositorio respondeu normalmente.
)

echo.
pause
