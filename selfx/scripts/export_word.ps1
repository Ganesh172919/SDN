param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
$wordApp=$null
$wordDoc=$null
try {
    $wordApp=New-Object -ComObject Word.Application
    $wordApp.Visible=$false
    $wordApp.DisplayAlerts=0
    $wordDoc=$wordApp.Documents.Open($InputPath,$false,$true)
    $wordDoc.ExportAsFixedFormat($OutputPath,17)
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) | Out-Null; [Runtime.InteropServices.Marshal]::ReleaseComObject($wordDoc) | Out-Null }
    if ($null -ne $wordApp) { $wordApp.Quit(); [Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) | Out-Null }
}
