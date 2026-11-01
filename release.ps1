$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$thumbprint = ($env:OPENSHARK_CERT_THUMBPRINT -replace '\s', '').ToUpperInvariant()
if (-not $thumbprint) {
    throw 'Defina OPENSHARK_CERT_THUMBPRINT com o thumbprint de um certificado confiável de assinatura de codigo antes de publicar.'
}
$certificate = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My |
    Where-Object { $_.Thumbprint -eq $thumbprint -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) } |
    Select-Object -First 1
if (-not $certificate) {
    throw 'Certificado de assinatura valido com chave privada nao encontrado.'
}
$signTool = if ($env:OPENSHARK_SIGNTOOL) { $env:OPENSHARK_SIGNTOOL } else { (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source }
if (-not $signTool -or -not (Test-Path -LiteralPath $signTool)) {
    throw 'signtool.exe nao encontrado. Configure OPENSHARK_SIGNTOOL com seu caminho.'
}
$iscc = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $iscc)) {
    throw 'Inno Setup 6 nao encontrado.'
}

& "$PSScriptRoot\build.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar OpenShark.exe' }
$app = Join-Path $PSScriptRoot 'OpenShark\dist\OpenShark.exe'
& $signTool sign /sha1 $thumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $app
if ($LASTEXITCODE -ne 0) { throw 'Falha ao assinar OpenShark.exe' }
& $iscc "$PSScriptRoot\installer.iss"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o instalador' }
$setup = Join-Path $PSScriptRoot 'OpenShark\dist\OpenShark-Setup-0.6.2.exe'
& $signTool sign /sha1 $thumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $setup
if ($LASTEXITCODE -ne 0) { throw 'Falha ao assinar o instalador' }
foreach ($file in @($app, $setup)) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $thumbprint) {
        throw "Assinatura invalida: $file ($($signature.Status))"
    }
}
Write-Host "Release 0.6.2 assinada: $setup"
