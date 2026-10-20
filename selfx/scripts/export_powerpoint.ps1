param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
$powerPointApp=$null
$powerPointDeck=$null
try {
    $powerPointApp=New-Object -ComObject PowerPoint.Application
    $powerPointDeck=$powerPointApp.Presentations.Open($InputPath,$true,$false,$false)
    $powerPointDeck.SaveAs($OutputPath,32)
} finally {
    if ($null -ne $powerPointDeck) { $powerPointDeck.Close(); [Runtime.InteropServices.Marshal]::ReleaseComObject($powerPointDeck) | Out-Null }
    if ($null -ne $powerPointApp) { $powerPointApp.Quit(); [Runtime.InteropServices.Marshal]::ReleaseComObject($powerPointApp) | Out-Null }
}
