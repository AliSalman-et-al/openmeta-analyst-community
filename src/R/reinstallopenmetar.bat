REM reinstall OpenMetaR script to run on windows

rm OpenMetaR_1.0.tar.gz
R CMD build OpenMetaR
R CMD INSTALL OpenMetaR_1.0.tar.gz
