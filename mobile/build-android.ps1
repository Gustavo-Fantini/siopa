param([ValidateSet('assembleDebug','lintDebug','testDebugUnitTest')][string]$Task = 'assembleDebug')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$androidProject = Join-Path $PSScriptRoot 'android'
$localJdk = Join-Path $projectRoot '.tools\android-build\jdk'
if (-not $env:JAVA_HOME -and (Test-Path -LiteralPath $localJdk)) {
    $env:JAVA_HOME = (Get-ChildItem -LiteralPath $localJdk -Directory | Select-Object -First 1).FullName
}
if (-not $env:JAVA_HOME -or -not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin\java.exe'))) {
    throw 'Configure JAVA_HOME com um JDK 17 ou 21, ou provisione o JDK em .tools/android-build/jdk.'
}
$localSdk = Join-Path $projectRoot '.tools\android-sdk'
if (Test-Path -LiteralPath $localSdk) { $env:ANDROID_SDK_ROOT = $localSdk }
if (-not $env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT = $env:ANDROID_HOME }
if (-not $env:ANDROID_SDK_ROOT) { throw 'Configure ANDROID_SDK_ROOT com o SDK Android (API 35 e Build Tools 34.0.0).' }
$env:ANDROID_USER_HOME = Join-Path $projectRoot '.tools\android-user'
$env:GRADLE_USER_HOME = Join-Path $projectRoot '.tools\gradle-cache'
$env:DEBUG = ''
$localGradle = Join-Path $projectRoot '.tools\android-build\gradle-8.9\bin\gradle.bat'
$ErrorActionPreference = 'Continue' # Native stderr warnings are not build failures; use the exit code.
if (Test-Path -LiteralPath $localGradle) { & $localGradle -p $androidProject --no-daemon --console=plain $Task }
else { & (Join-Path $androidProject 'gradlew.bat') -p $androidProject --no-daemon --console=plain $Task }
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Task -eq 'assembleDebug') {
    $apk = Join-Path $androidProject 'app\build\outputs\apk\debug\app-debug.apk'
    Get-Item -LiteralPath $apk | Select-Object FullName,Length
    Get-FileHash -LiteralPath $apk -Algorithm SHA256
}
