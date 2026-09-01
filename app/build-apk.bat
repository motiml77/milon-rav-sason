@echo off
set "ANDROID_HOME=C:\Users\Moti Levi\AppData\Local\Android\Sdk"
set "JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
set "GRADLE_USER_HOME=C:\gradle-tmp\.gradle"
set "GRADLE_OPTS=-Djava.io.tmpdir=C:\gradle-tmp -Djdk.net.unixdomain.tmpdir=C:\gradle-tmp"
set "TEMP=C:\gradle-tmp"
set "TMP=C:\gradle-tmp"

cd /d "%~dp0"

REM 1. www טרי מ-milon.html שבשורש. בלי זה בונים תוכן ישן.
call node ..\scripts\build-www.mjs www
if errorlevel 1 goto err

REM 2. העתקה לתוך פרויקט אנדרואיד. גרדל לבדו *לא* עושה את זה,
REM    ובלי השלב הזה ה-APK נבנה בשקט מנכסים ישנים.
call npx cap copy android
if errorlevel 1 goto err

cd /d "%~dp0android"
call .\gradlew.bat assembleDebug --no-daemon
echo EXIT_CODE=%ERRORLEVEL%
goto :eof

:err
echo.
echo ***  הבנייה בוטלה — שלב ההכנה נכשל  ***
exit /b 1
