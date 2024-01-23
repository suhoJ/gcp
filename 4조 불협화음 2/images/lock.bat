@ECHO OFF
if EXIST "Locker" goto UNLOCK
if NOT EXIST Locker mkdir Locker
echo Enter password to lock folder
set/p "pass=>"
if %pass%==gcp goto LOCK
goto END

:UNLOCK
echo Enter password to unlock folder
set/p "pass=>"
if %pass%==gcp goto START
goto FAIL

:LOCK
ren Locker "Control Panel.{21EC2020-3AEA-1069-A2DD-08002B30309D}"
attrib +h +s "Control Panel.{21EC2020-3AEA-1069-A2DD-08002B30309D}"
echo Folder locked
goto End

:START
attrib -h -s "Control Panel.{21EC2020-3AEA-1069-A2DD-08002B30309D}"
ren "Control Panel.{21EC2020-3AEA-1069-A2DD-08002B30309D}" Locker
echo Folder Unlocked successfully
goto End

:FAIL
echo Invalid password
goto end

:End
