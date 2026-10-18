$ver = (Get-Content VERSION | Select-Object -First 1).Trim()
Write-Output $ver
