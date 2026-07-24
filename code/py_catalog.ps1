param (
    [string]$RootFolder = ".",
    [string[]]$ExcludeKeywords = @("venv", "__pycache__")
)

# Resolve full path
$RootFolder = (Resolve-Path $RootFolder).Path

# Name output file after the folder being scanned
$FolderName = Split-Path $RootFolder -Leaf
$OutputFile = "$FolderName.txt"

# Get all .py files recursively
$files = Get-ChildItem -Path $RootFolder -Recurse -Filter *.py -File | Where-Object {
    $fullPath = $_.FullName

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

        Add-Content -Path $OutputFile -Value "===== FILE START: $($file.FullName) ====="
        Add-Content -Path $OutputFile -Value $content
        Add-Content -Path $OutputFile -Value "===== FILE END =====`r`n"
    }
    catch {
        Write-Warning "Failed to read file: $($file.FullName)"
    }
}

Write-Host "Done. Output written to $OutputFile"