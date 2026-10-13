@echo off
rem Dat file nay o COWORK\BO_CONG_CU_TU_DONG_HOA_BOM\  Goi: dieu_phoi tiep --den-het
rem Khong dung bien $ (Desktop Commander lam mat ky tu $), duong dan Python ghi thang.
chcp 65001 >nul
"C:\Users\accountsf\AppData\Local\Programs\Python\Python311\python.exe" -X utf8 -B "%~dp0SCRIPTS\dieu_phoi.py" %*
exit /b %ERRORLEVEL%
