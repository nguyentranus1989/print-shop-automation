# PrintFlow Agent - Setup Wizard (WPF GUI)
# Modern UI with folder browser, auto-detection, writes agent.toml.

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms

# Modern folder picker (Vista+ Explorer-style with address bar)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

[ComImport, Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")] class FOS_CLS { }

[ComImport, Guid("42F85136-DB7E-439C-85F1-E4075D135FC8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IFileOpenDialog {
    [PreserveSig] int Show(IntPtr hwnd);
    void SetFileTypes(uint cTypes, IntPtr rgFilterSpec);
    void SetFileTypeIndex(uint iIndex);
    void GetFileTypeIndex(out uint piIndex);
    void Advise(IntPtr pfde, out uint pdwCookie);
    void Unadvise(uint dwCookie);
    void SetOptions(uint fos);
    void GetOptions(out uint pfos);
    void SetDefaultFolder(IShellItem psi);
    void SetFolder(IShellItem psi);
    void GetFolder(out IShellItem ppsi);
    void GetCurrentSelection(out IShellItem ppsi);
    void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
    void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
    void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
    void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
    void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
    void GetResult(out IShellItem ppsi);
    void AddPlace(IShellItem psi, int fdap);
    void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string pszExt);
    void Close(int hr);
    void SetClientGuid([In] ref Guid guid);
    void ClearClientData();
    void SetFilter(IntPtr pFilter);
    void GetResults(out IntPtr ppenum);
    void GetSelectedItems(out IntPtr ppsai);
}

[ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IShellItem {
    void BindToHandler(IntPtr pbc, [MarshalAs(UnmanagedType.LPStruct)] Guid bhid, [MarshalAs(UnmanagedType.LPStruct)] Guid riid, out IntPtr ppv);
    void GetParent(out IShellItem ppsi);
    void GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
    void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
    void Compare(IShellItem psi, uint hint, out int piOrder);
}

public class ModernFolderPicker {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHCreateItemFromParsingName(string pszPath, IntPtr pbc, [MarshalAs(UnmanagedType.LPStruct)] Guid riid, out IShellItem ppv);

    public static string Show(string title, string initialPath) {
        var dlg = (IFileOpenDialog)new FOS_CLS();
        dlg.SetOptions(0x20 | 0x40 | 0x800); // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_FILEMUSTEXIST
        dlg.SetTitle(title ?? "Select Folder");
        dlg.SetOkButtonLabel("Select");

        if (!string.IsNullOrEmpty(initialPath)) {
            IShellItem folder;
            if (SHCreateItemFromParsingName(initialPath, IntPtr.Zero, typeof(IShellItem).GUID, out folder) == 0)
                dlg.SetFolder(folder);
        }

        if (dlg.Show(IntPtr.Zero) != 0) return null;

        IShellItem result;
        dlg.GetResult(out result);
        string path;
        result.GetDisplayName(0x80058000, out path);
        return path;
    }
}
"@ -ReferencedAssemblies PresentationFramework

# --- Resolve output directory ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = $scriptDir

if (Test-Path (Join-Path $root "agent\printflow-agent.exe")) {
    $agentDir = Join-Path $root "agent"
} elseif (Test-Path (Join-Path (Split-Path $root -Parent) "agent\printflow-agent.exe")) {
    $root = Split-Path $root -Parent
    $agentDir = Join-Path $root "agent"
} elseif (Test-Path (Join-Path (Split-Path $root -Parent) "dist\printflow-agent\printflow-agent.exe")) {
    $root = Split-Path $root -Parent
    $agentDir = Join-Path $root "dist\printflow-agent"
} else {
    $agentDir = $root
}

$tomlPath = Join-Path $agentDir "agent.toml"

# --- Detection functions ---
function Detect-PrinterType($folder) {
    if (-not $folder -or -not (Test-Path $folder)) { return @("auto", "Path not found") }
    if (Test-Path (Join-Path $folder "CraftFlow.dll")) { return @("uv", "CraftFlow.dll found") }
    if (Test-Path (Join-Path $folder "UVDevice.dll")) { return @("uv", "UVDevice.dll found") }
    if (Test-Path (Join-Path $folder "DTFDevice.dll")) { return @("dtf", "DTFDevice.dll found") }
    $exe64 = Join-Path $folder "PrintExp_X64.exe"
    $exe32 = Join-Path $folder "PrintExp.exe"
    if (Test-Path $exe64) { return @("dtf", "64-bit executable") }
    if (Test-Path $exe32) { return @("dtg", "32-bit executable") }
    if (Test-Path (Join-Path $folder "KRemoteMonitor.dll")) { return @("dtf", "KRemoteMonitor.dll found") }
    return @("dtg", "Default")
}

function Find-PrintExpExe($folder) {
    if (-not $folder) { return "" }
    $exe64 = Join-Path $folder "PrintExp_X64.exe"
    $exe32 = Join-Path $folder "PrintExp.exe"
    if (Test-Path $exe64) { return $exe64 }
    if (Test-Path $exe32) { return $exe32 }
    return (Join-Path $folder "PrintExp.exe")
}

# --- Pre-detect path ---
$defaultPath = ""
$commonPaths = @(
    "C:\PrintExp_5.7.7.1.12_MULTIWS",
    "C:\PrintExp",
    "D:\PrintExp",
    "$env:USERPROFILE\Projects\DTG_autommation\PrintExp_5.7.7.1.12_MULTIWS"
)
foreach ($p in $commonPaths) {
    $expanded = [Environment]::ExpandEnvironmentVariables($p)
    if (Test-Path $expanded) { $defaultPath = $expanded; break }
}

$initDetect = Detect-PrinterType $defaultPath
$initType = $initDetect[0]
$initReason = $initDetect[1]

# Map type to combo index
$typeIndex = @{"dtg"=0; "dtf"=1; "uv"=2}
$selectedIdx = if ($typeIndex.ContainsKey($initType)) { $typeIndex[$initType] } else { 0 }

# --- XAML UI ---
[xml]$xaml = @"
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="PrintFlow Agent Setup"
    Width="560" Height="540"
    SizeToContent="Height"
    WindowStartupLocation="CenterScreen"
    ResizeMode="NoResize"
    Background="#FAFAFA">

    <Window.Resources>
        <Style x:Key="LabelStyle" TargetType="TextBlock">
            <Setter Property="FontSize" Value="13"/>
            <Setter Property="FontWeight" Value="SemiBold"/>
            <Setter Property="Foreground" Value="#333"/>
            <Setter Property="Margin" Value="0,0,0,6"/>
        </Style>
        <Style x:Key="HintStyle" TargetType="TextBlock">
            <Setter Property="FontSize" Value="11.5"/>
            <Setter Property="Foreground" Value="#888"/>
            <Setter Property="Margin" Value="0,4,0,0"/>
        </Style>
        <Style x:Key="InputStyle" TargetType="TextBox">
            <Setter Property="FontSize" Value="13"/>
            <Setter Property="Padding" Value="8,6"/>
            <Setter Property="BorderBrush" Value="#CCC"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="Background" Value="White"/>
        </Style>
        <Style x:Key="ComboStyle" TargetType="ComboBox">
            <Setter Property="FontSize" Value="13"/>
            <Setter Property="Padding" Value="8,6"/>
            <Setter Property="BorderBrush" Value="#CCC"/>
            <Setter Property="Background" Value="White"/>
        </Style>
    </Window.Resources>

    <Grid Margin="28,20,28,20">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <!-- Title -->
        <StackPanel Grid.Row="0" Margin="0,0,0,4">
            <TextBlock FontSize="20" FontWeight="Bold" Foreground="#1a1a1a">PrintFlow Agent Setup</TextBlock>
            <TextBlock FontSize="12" Foreground="#777" Margin="0,4,0,0">Configure the agent for your printer workstation</TextBlock>
        </StackPanel>

        <!-- Separator -->
        <Border Grid.Row="1" BorderBrush="#E0E0E0" BorderThickness="0,0,0,1" Margin="0,8,0,16"/>

        <!-- PrintExp Path -->
        <StackPanel Grid.Row="2" Margin="0,0,0,16">
            <TextBlock Style="{StaticResource LabelStyle}">PrintExp Installation Folder</TextBlock>
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>
                <TextBox x:Name="txtPath" Grid.Column="0" Style="{StaticResource InputStyle}" Text="$defaultPath"/>
                <Button x:Name="btnBrowse" Grid.Column="1" Content="Browse" Padding="16,6" Margin="8,0,0,0"
                        FontSize="13" Background="#F0F0F0" BorderBrush="#CCC" Cursor="Hand"/>
            </Grid>
        </StackPanel>

        <!-- Printer Type -->
        <StackPanel Grid.Row="3" Margin="0,0,0,16">
            <TextBlock Style="{StaticResource LabelStyle}">Printer Type</TextBlock>
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="Auto"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>
                <ComboBox x:Name="cmbType" Grid.Column="0" Style="{StaticResource ComboStyle}" Width="120"
                          SelectedIndex="$selectedIdx">
                    <ComboBoxItem Content="DTG"/>
                    <ComboBoxItem Content="DTF"/>
                    <ComboBoxItem Content="UV"/>
                </ComboBox>
                <TextBlock x:Name="lblDetected" Grid.Column="1" VerticalAlignment="Center" Margin="12,0,0,0"
                           FontSize="12" Foreground="#2E7D32">Detected: $($initType.ToUpper()) - $initReason</TextBlock>
            </Grid>
        </StackPanel>

        <!-- Port -->
        <StackPanel Grid.Row="4" Margin="0,0,0,16">
            <TextBlock Style="{StaticResource LabelStyle}">Agent HTTP Port</TextBlock>
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="Auto"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>
                <TextBox x:Name="txtPort" Grid.Column="0" Style="{StaticResource InputStyle}" Text="8080" Width="100"/>
                <TextBlock Grid.Column="1" Style="{StaticResource HintStyle}" VerticalAlignment="Center"
                           Margin="12,0,0,0">Default: 8080. Change if running multiple agents.</TextBlock>
            </Grid>
        </StackPanel>

        <!-- Dashboard URL -->
        <StackPanel Grid.Row="5" Margin="0,0,0,16">
            <TextBlock Style="{StaticResource LabelStyle}">Dashboard Address</TextBlock>
            <TextBox x:Name="txtDashboard" Style="{StaticResource InputStyle}" Text="http://localhost:8000"/>
            <TextBlock Style="{StaticResource HintStyle}">URL of the central dashboard. Use localhost for same PC, or the dashboard PC's IP.</TextBlock>
        </StackPanel>

        <!-- Agent Name -->
        <StackPanel Grid.Row="6" Margin="0,0,0,16">
            <TextBlock Style="{StaticResource LabelStyle}">Agent Display Name</TextBlock>
            <TextBox x:Name="txtName" Style="{StaticResource InputStyle}" Text="PrintFlow-Agent"/>
            <TextBlock Style="{StaticResource HintStyle}">Shown in the dashboard. e.g. "DTG Left", "Printer-01"</TextBlock>
        </StackPanel>

        <!-- Separator -->
        <Border Grid.Row="8" BorderBrush="#E0E0E0" BorderThickness="0,0,0,1" Margin="0,0,0,12" VerticalAlignment="Bottom"/>

        <!-- Buttons -->
        <StackPanel Grid.Row="9" Orientation="Horizontal" HorizontalAlignment="Right">
            <Button x:Name="btnCancel" Content="Cancel" Padding="20,8" FontSize="13"
                    Background="#F0F0F0" BorderBrush="#CCC" Cursor="Hand" Margin="0,0,10,0"/>
            <Button x:Name="btnSave" Content="Save and Start Agent" Padding="24,8" FontSize="13" FontWeight="SemiBold"
                    Background="#0078D4" Foreground="White" BorderBrush="#0078D4" Cursor="Hand"/>
        </StackPanel>
    </Grid>
</Window>
"@

# --- Load XAML ---
$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [System.Windows.Markup.XamlReader]::Load($reader)

# --- Get controls ---
$txtPath = $window.FindName("txtPath")
$btnBrowse = $window.FindName("btnBrowse")
$cmbType = $window.FindName("cmbType")
$lblDetected = $window.FindName("lblDetected")
$txtPort = $window.FindName("txtPort")
$txtDashboard = $window.FindName("txtDashboard")
$txtName = $window.FindName("txtName")
$btnSave = $window.FindName("btnSave")
$btnCancel = $window.FindName("btnCancel")

# --- Events ---
$btnBrowse.Add_Click({
    $initDir = if ($txtPath.Text -and (Test-Path $txtPath.Text)) { $txtPath.Text } else { "C:\" }
    $selected = [ModernFolderPicker]::Show("Select PrintExp Installation Folder", $initDir)
    if ($selected) {
        $txtPath.Text = $selected
        $result = Detect-PrinterType $selected
        $typeMap = @{"dtg"=0; "dtf"=1; "uv"=2}
        if ($typeMap.ContainsKey($result[0])) { $cmbType.SelectedIndex = $typeMap[$result[0]] }
        $lblDetected.Text = "Detected: $($result[0].ToUpper()) - $($result[1])"
    }
})

$btnCancel.Add_Click({
    $window.Tag = "cancelled"
    $window.Close()
})

$btnSave.Add_Click({
    # Validate path
    if (-not $txtPath.Text -or -not (Test-Path $txtPath.Text)) {
        [System.Windows.MessageBox]::Show("Please select a valid PrintExp folder.", "PrintFlow Setup", "OK", "Warning")
        return
    }

    # Validate port
    $port = $txtPort.Text
    if (-not ($port -match '^\d+$') -or [int]$port -lt 1 -or [int]$port -gt 65535) {
        [System.Windows.MessageBox]::Show("Port must be a number between 1 and 65535.", "PrintFlow Setup", "OK", "Warning")
        return
    }

    # Get values
    $exePath = (Find-PrintExpExe $txtPath.Text) -replace '\\','\\'
    $agentName = if ($txtName.Text) { $txtName.Text } else { "PrintFlow-Agent" }
    $dashboardUrl = if ($txtDashboard.Text) { $txtDashboard.Text.TrimEnd('/') } else { "http://localhost:8000" }
    $typeNames = @("dtg", "dtf", "uv")
    $printerType = $typeNames[$cmbType.SelectedIndex]

    # Write TOML
    $toml = @"
[agent]
name = "$agentName"
poll_interval_seconds = 5

[printer]
type = "$printerType"

[printexp]
exe_path = "$exePath"
tcp_port = 9100
memory_offset = 0x016CDB

[network]
port = $port
dashboard_url = "$dashboardUrl"

[files]
nas_path = "\\\\nas\\prn-files"
temp_path = "C:\\Hstemp"
"@

    $toml | Out-File -FilePath $tomlPath -Encoding UTF8 -Force
    $window.Tag = "saved"
    $window.Close()
})

# --- Show ---
$window.ShowDialog() | Out-Null

if ($window.Tag -eq "saved") {
    Write-Host "[setup] Config saved to: $tomlPath"
    exit 0
} else {
    Write-Host "[setup] Cancelled."
    exit 1
}
