param (
    [string]$RootFolder = ".",
    [string]$OutputFile = "all_py_files .txt",
    [string[]]$ExcludeKeywords = @("venv", "__pycache__")  # Modify as needed
)

# Resolve full path
$RootFolder = Resolve-Path $RootFolder

# Get all .py files recursively
$files = Get-ChildItem -Path $RootFolder -Recurse -Filter *.py -File | Where-Object {
    $fullPath = $_.FullName
    # Exclude any file where path contains any keyword
    foreach ($keyword in $ExcludeKeywords) {
        if ($fullPath -like "*$keyword*") {
            return $false
        }
    }
    return $true
}

# Clear or create output file
"" | Out-File -FilePath $OutputFile -Encoding utf8

foreach ($file in $files) {
    try {
        $content = Get-Content -Path $file.FullName -Raw

        Add-Content -Path $OutputFile -Value "$($file.FullName):"
        Add-Content -Path $OutputFile -Value $content
        Add-Content -Path $OutputFile -Value "`r`n"  # 2x newline spacing
    }
    catch {
        Write-Warning "Failed to read file: $($file.FullName)"
    }
}

Write-Host "Done. Output written to $OutputFile"