@echo off
set "ANDROID_HOME=C:\Users\Moti Levi\AppData\Local\Android\Sdk"
set "JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
set "GRADLE_USER_HOME=C:\gradle-tmp\.gradle"
set "GRADLE_OPTS=-Djava.io.tmpdir=C:\gradle-tmp -Djdk.net.unixdomain.tmpdir=C:\gradle-tmp"
set "TEMP=C:\gradle-tmp"
set "TMP=C:\gradle-tmp"
cd /d "C:\Users\Moti Levi\Desktop\AI\rav sason\.claude\worktrees\site-audit-search-optimization-a16a0e\app\android"
call .\gradlew.bat assembleDebug --no-daemon
echo EXIT_CODE=%ERRORLEVEL%
