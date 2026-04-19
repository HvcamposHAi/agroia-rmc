# Setup script para configurar ANTHROPIC_API_KEY no Windows PowerShell
# Execute este arquivo para adicionar a chave ao ambiente permanentemente

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiKey
)

if (-not $ApiKey) {
    Write-Host "Digite sua ANTHROPIC_API_KEY (sk-ant-...):"
    $ApiKey = Read-Host "API Key"
}

if ($ApiKey.StartsWith("sk-ant-")) {
    # Adicionar ao ambiente do usuário (persistente)
    [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $ApiKey, "User")

    # Também definir na sessão atual
    $env:ANTHROPIC_API_KEY = $ApiKey

    Write-Host "✓ ANTHROPIC_API_KEY configurada com sucesso!"
    Write-Host "  (Será persistente após reiniciar o terminal)"
    Write-Host ""
    Write-Host "Para usar agora na sessão atual, a chave já está configurada."
} else {
    Write-Host "✗ Chave inválida. Deve começar com 'sk-ant-'"
}
