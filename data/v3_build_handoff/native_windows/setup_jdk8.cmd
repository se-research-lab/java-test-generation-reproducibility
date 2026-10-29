@echo off
rem This file intentionally does not use SETLOCAL: CALL it when the variables
rem must remain active in the current CMD session.

if not defined JDK8_HOME set "JDK8_HOME=C:\Program Files\Java\jdk1.8.0_172"
if not defined MAVEN_3915_HOME set "MAVEN_3915_HOME=C:\Program Files\apache-maven-3.9.15"

if not exist "%JDK8_HOME%\bin\java.exe" (
  echo STOP: java.exe not found under JDK8_HOME="%JDK8_HOME%"
  echo Set JDK8_HOME to a complete JDK 8 installation, not a standalone JRE.
  exit /b 1
)

if not exist "%JDK8_HOME%\bin\javac.exe" (
  echo STOP: javac.exe not found under JDK8_HOME="%JDK8_HOME%"
  echo A standalone jre1.8 directory cannot compile the repositories.
  exit /b 1
)

if not exist "%MAVEN_3915_HOME%\bin\mvn.cmd" (
  echo STOP: Maven 3.9.15 not found under MAVEN_3915_HOME="%MAVEN_3915_HOME%"
  exit /b 1
)

set "JAVA_HOME=%JDK8_HOME%"
set "MAVEN_HOME=%MAVEN_3915_HOME%"
set "PATH=%JAVA_HOME%\bin;%MAVEN_HOME%\bin;%PATH%"

echo JAVA_HOME=%JAVA_HOME%
where java
where javac
where mvn
java -version
javac -version
mvn -version

exit /b %ERRORLEVEL%
