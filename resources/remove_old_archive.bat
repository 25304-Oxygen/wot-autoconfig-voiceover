@echo off
setlocal enabledelayedexpansion

:: ������DeepSeek���ɡ������ǽ��鵵�ļ��滻�����ļ�
:: ������"autoConfigVoiceOver"��ͷ���ļ�
set "targetfile="
for %%f in ("autoConfigVoiceOver*") do (
    set "targetfile=%%f"
    goto :found
)

:found
if not defined targetfile (
    echo û���ҵ��� autoConfigVoiceOver ��ͷ���ļ�
    pause
    exit /b
)

:: �ȼ��temp.zip�Ƿ����
if not exist "temp.zip" (
    echo δ�ҵ�temp.zip�ļ���������ֹ
    echo ��ɸ��º���Զ��Ƴ�temp.zip���������ʱ�򲻻�����temp.zip
    pause
    exit /b 1
)

echo �ҵ�Ŀ���ļ�: %targetfile%
echo �����ĵȴ��ļ����¡���

:: ����ɾ���ļ�ֱ���ɹ�
:deleteLoop
del "%targetfile%" >nul 2>&1
if exist "%targetfile%" (
    ping -n 2 127.0.0.1 >nul
    goto :deleteLoop
)

echo �ɹ�ɾ���ļ�: %targetfile%

:: ������temp.zipΪ��ɾ�����ļ���
if exist "temp.zip" (
    ren "temp.zip" "%targetfile%"
    echo �ѽ�temp.zip������Ϊ: %targetfile%
) else (
    echo δ�ҵ�temp.zip�ļ�
    pause
)