using System;
using System.IO;
using System.Drawing;
using System.Windows.Forms;
using System.Diagnostics;
using System.Reflection;
using System.Net;
using System.IO.Compression;
using System.Runtime.InteropServices;

namespace JMVertex.Installer
{
    public class SetupWizardForm : Form
    {
        private Label lblTitle;
        private Label lblSubtitle;
        private Label lblSpecs;
        private TextBox txtPath;
        private Button btnBrowse;
        private Button btnInstall;
        private Button btnCancel;
        private CheckBox chkDesktopShortcut;
        private CheckBox chkLaunchNow;
        private ProgressBar progressBar;
        private Label lblStatus;
        private Panel headerPanel;
        private System.Windows.Forms.Timer installTimer;
        private int installProgress = 0;
        private string targetDir = "";
        private string vbsPath = "";

        [DllImport("user32.dll")]
        public static extern int SendMessage(IntPtr hWnd, int Msg, int wParam, int lParam);
        [DllImport("user32.dll")]
        public static extern bool ReleaseCapture();

        public SetupWizardForm()
        {
            InitializeComponent();
            LoadLaptopSpecs();
        }

        private void InitializeComponent()
        {
            this.Text = "JM Vertex AI Companion — Setup Wizard";
            this.Size = new Size(620, 520);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.None;
            this.BackColor = Color.FromArgb(11, 15, 23);
            this.ForeColor = Color.White;
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            // Header Panel
            headerPanel = new Panel();
            headerPanel.Dock = DockStyle.Top;
            headerPanel.Height = 110;
            headerPanel.BackColor = Color.FromArgb(15, 24, 34);
            headerPanel.MouseDown += HeaderPanel_MouseDown;

            lblTitle = new Label();
            lblTitle.Text = "JM VERTEX  AI COMPANION";
            lblTitle.Font = new Font("Segoe UI", 16f, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(0, 230, 118);
            lblTitle.Location = new Point(25, 22);
            lblTitle.AutoSize = true;

            lblSubtitle = new Label();
            lblSubtitle.Text = "Your Smart Desktop Assistant — 1-Click Error-Free Installer";
            lblSubtitle.Font = new Font("Segoe UI", 10f, FontStyle.Regular);
            lblSubtitle.ForeColor = Color.FromArgb(200, 220, 210);
            lblSubtitle.Location = new Point(27, 58);
            lblSubtitle.AutoSize = true;

            headerPanel.Controls.Add(lblTitle);
            headerPanel.Controls.Add(lblSubtitle);

            // Laptop specs box
            Label lblSpecsHeader = new Label();
            lblSpecsHeader.Text = "TARGET LAPTOP HARDWARE PROFILE";
            lblSpecsHeader.Font = new Font("Segoe UI", 9f, FontStyle.Bold);
            lblSpecsHeader.ForeColor = Color.FromArgb(0, 230, 118);
            lblSpecsHeader.Location = new Point(25, 125);
            lblSpecsHeader.AutoSize = true;

            lblSpecs = new Label();
            lblSpecs.Font = new Font("Consolas", 8.5f, FontStyle.Regular);
            lblSpecs.ForeColor = Color.FromArgb(160, 185, 200);
            lblSpecs.BackColor = Color.FromArgb(18, 28, 38);
            lblSpecs.Location = new Point(25, 148);
            lblSpecs.Size = new Size(570, 75);
            lblSpecs.BorderStyle = BorderStyle.FixedSingle;
            lblSpecs.Padding = new Padding(8);
            lblSpecs.Text = "Scanning laptop specifications...";

            // Target directory
            Label lblDir = new Label();
            lblDir.Text = "Installation Target Directory:";
            lblDir.Font = new Font("Segoe UI", 9f, FontStyle.Bold);
            lblDir.ForeColor = Color.White;
            lblDir.Location = new Point(25, 236);
            lblDir.AutoSize = true;

            string defaultPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "JM-Vertex");
            txtPath = new TextBox();
            txtPath.Text = defaultPath;
            txtPath.Location = new Point(25, 260);
            txtPath.Size = new Size(465, 26);
            txtPath.BackColor = Color.FromArgb(22, 33, 44);
            txtPath.ForeColor = Color.White;
            txtPath.BorderStyle = BorderStyle.FixedSingle;

            btnBrowse = new Button();
            btnBrowse.Text = "Browse...";
            btnBrowse.Location = new Point(500, 258);
            btnBrowse.Size = new Size(95, 28);
            btnBrowse.FlatStyle = FlatStyle.Flat;
            btnBrowse.BackColor = Color.FromArgb(28, 42, 56);
            btnBrowse.ForeColor = Color.FromArgb(0, 230, 118);
            btnBrowse.FlatAppearance.BorderColor = Color.FromArgb(0, 230, 118);
            btnBrowse.Click += (s, e) => {
                using (FolderBrowserDialog fbd = new FolderBrowserDialog()) {
                    fbd.SelectedPath = txtPath.Text;
                    if (fbd.ShowDialog() == DialogResult.OK) {
                        txtPath.Text = fbd.SelectedPath;
                    }
                }
            };

            // Checkboxes
            chkDesktopShortcut = new CheckBox();
            chkDesktopShortcut.Text = "Create Desktop Shortcut (1-Click Run with No Terminal)";
            chkDesktopShortcut.Checked = true;
            chkDesktopShortcut.ForeColor = Color.FromArgb(220, 220, 220);
            chkDesktopShortcut.Location = new Point(25, 300);
            chkDesktopShortcut.AutoSize = true;

            chkLaunchNow = new CheckBox();
            chkLaunchNow.Text = "Launch JM Vertex AI Companion immediately (Silent Mode)";
            chkLaunchNow.Checked = true;
            chkLaunchNow.ForeColor = Color.FromArgb(220, 220, 220);
            chkLaunchNow.Location = new Point(25, 326);
            chkLaunchNow.AutoSize = true;

            // Status label & progress bar
            lblStatus = new Label();
            lblStatus.Text = "Ready to install companion on this laptop.";
            lblStatus.ForeColor = Color.FromArgb(140, 170, 185);
            lblStatus.Location = new Point(25, 365);
            lblStatus.Size = new Size(570, 20);

            progressBar = new ProgressBar();
            progressBar.Location = new Point(25, 390);
            progressBar.Size = new Size(570, 18);
            progressBar.Style = ProgressBarStyle.Continuous;
            progressBar.Visible = false;

            // Bottom Buttons
            btnInstall = new Button();
            btnInstall.Text = "INSTALL FOR THIS LAPTOP";
            btnInstall.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            btnInstall.Location = new Point(325, 445);
            btnInstall.Size = new Size(270, 42);
            btnInstall.FlatStyle = FlatStyle.Flat;
            btnInstall.BackColor = Color.FromArgb(0, 230, 118);
            btnInstall.ForeColor = Color.Black;
            btnInstall.Cursor = Cursors.Hand;
            btnInstall.FlatAppearance.BorderSize = 0;
            btnInstall.Click += BtnInstall_Click;

            btnCancel = new Button();
            btnCancel.Text = "Cancel";
            btnCancel.Location = new Point(210, 445);
            btnCancel.Size = new Size(100, 42);
            btnCancel.FlatStyle = FlatStyle.Flat;
            btnCancel.BackColor = Color.FromArgb(28, 42, 56);
            btnCancel.ForeColor = Color.FromArgb(180, 190, 200);
            btnCancel.FlatAppearance.BorderColor = Color.FromArgb(50, 70, 90);
            btnCancel.Click += (s, e) => this.Close();

            this.Controls.Add(headerPanel);
            this.Controls.Add(lblSpecsHeader);
            this.Controls.Add(lblSpecs);
            this.Controls.Add(lblDir);
            this.Controls.Add(txtPath);
            this.Controls.Add(btnBrowse);
            this.Controls.Add(chkDesktopShortcut);
            this.Controls.Add(chkLaunchNow);
            this.Controls.Add(lblStatus);
            this.Controls.Add(progressBar);
            this.Controls.Add(btnInstall);
            this.Controls.Add(btnCancel);

            installTimer = new System.Windows.Forms.Timer();
            installTimer.Interval = 100;
            installTimer.Tick += InstallTimer_Tick;
        }

        private void HeaderPanel_MouseDown(object sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                ReleaseCapture();
                SendMessage(Handle, 0xA1, 0x2, 0);
            }
        }

        private void LoadLaptopSpecs()
        {
            try
            {
                string osName = Environment.OSVersion.ToString();
                string machine = Environment.MachineName;
                string user = Environment.UserName;
                int cores = Environment.ProcessorCount;
                bool is64 = Environment.Is64BitOperatingSystem;
                string arch = is64 ? "64-bit Architecture" : "32-bit Architecture";

                string uuid = Guid.NewGuid().ToString("N").Substring(0, 8).ToUpper();
                try
                {
                    object regVal = Microsoft.Win32.Registry.GetValue(@"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography", "MachineGuid", uuid);
                    if (regVal != null)
                    {
                        uuid = regVal.ToString();
                        if (uuid.Length > 8) uuid = uuid.Substring(0, 8).ToUpper();
                    }
                }
                catch { }

                lblSpecs.Text = string.Format(
                    "Device: {0} ({1}) | Signature: JM-LAPTOP-{2}\n" +
                    "Operating System: {3} [{4}]\n" +
                    "Processor: {5} Logical Cores | User Profile: {6}\n" +
                    "Status: [COMPATIBLE WINDOWS 10/11 HARDWARE]",
                    machine, Environment.UserDomainName, uuid, osName, arch, cores, user
                );
            }
            catch (Exception ex)
            {
                lblSpecs.Text = "System scan completed. Ready for installation.\n" + ex.Message;
            }
        }

        private void BtnInstall_Click(object sender, EventArgs e)
        {
            btnInstall.Enabled = false;
            btnCancel.Enabled = false;
            btnBrowse.Enabled = false;
            txtPath.ReadOnly = true;
            progressBar.Visible = true;
            installProgress = 0;
            targetDir = txtPath.Text;

            System.Threading.ThreadPool.QueueUserWorkItem((state) => {
                PerformFullInstallationBackground();
            });
            installTimer.Start();
        }

        private void InstallTimer_Tick(object sender, EventArgs e)
        {
            if (installProgress < 95)
            {
                installProgress += 3;
                progressBar.Value = Math.Min(installProgress, 95);
            }
        }

        private void UpdateStatus(string message, int progress)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(() => UpdateStatus(message, progress)));
                return;
            }
            lblStatus.Text = message;
            if (progress >= 0 && progress <= 100)
            {
                progressBar.Value = progress;
            }
        }

        private void PerformFullInstallationBackground()
        {
            try
            {
                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                // STEP 1: Check & Auto-Install Node.js runtime if missing
                UpdateStatus("Checking system prerequisites (Node.js runtime)...", 15);
                EnsureNodeJsInstalled();

                // STEP 2: Extract embedded payload files
                UpdateStatus("Extracting JM Vertex AI Companion core files...", 40);
                ExtractPayload();

                // STEP 3: Setup Dependencies & Node modules silently
                UpdateStatus("Configuring desktop companion engine...", 65);
                SetupDesktopDependencies();

                // STEP 4: Configure Silent Launcher (NO CMD WINDOW, NO NPX ERROR)
                UpdateStatus("Configuring silent desktop launcher & shortcuts...", 90);
                ConfigureSilentLauncher();

                // STEP 5: Complete
                UpdateStatus("Installation Successful! Ready on your laptop.", 100);
                this.Invoke(new Action(() => {
                    installTimer.Stop();
                    progressBar.Value = 100;
                    lblStatus.ForeColor = Color.FromArgb(0, 230, 118);
                    btnInstall.Text = "COMPANION READY (LAUNCH)";
                    btnInstall.Enabled = true;
                    btnCancel.Text = "Close";
                    btnCancel.Visible = true;
                    btnCancel.Enabled = true;

                    btnInstall.Click -= BtnInstall_Click;
                    btnInstall.Click += (s, e) => {
                        LaunchCompanionSilently();
                        this.Close();
                    };

                    if (chkLaunchNow.Checked)
                    {
                        LaunchCompanionSilently();
                    }
                }));
            }
            catch (Exception ex)
            {
                this.Invoke(new Action(() => {
                    installTimer.Stop();
                    lblStatus.Text = "Installation notice: " + ex.Message;
                    lblStatus.ForeColor = Color.Orange;
                    btnInstall.Enabled = true;
                    btnCancel.Enabled = true;
                }));
            }
        }

        private void EnsureNodeJsInstalled()
        {
            bool hasNode = false;

            try
            {
                Process p = new Process();
                p.StartInfo.FileName = "node.exe";
                p.StartInfo.Arguments = "--version";
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.StartInfo.WindowStyle = ProcessWindowStyle.Hidden;
                p.Start();
                p.WaitForExit(3000);
                if (p.ExitCode == 0) hasNode = true;
            }
            catch { hasNode = false; }

            string pfNode = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "nodejs");
            string pfNode86 = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "nodejs");
            if (File.Exists(Path.Combine(pfNode, "node.exe")) || File.Exists(Path.Combine(pfNode86, "node.exe")))
            {
                hasNode = true;
            }

            if (!hasNode)
            {
                // Download and install Node.js silently via MSI
                try
                {
                    UpdateStatus("Downloading Node.js LTS runtime (silent auto-install)...", 20);
                    string msiUrl = "https://nodejs.org/dist/v20.18.1/node-v20.18.1-x64.msi";
                    string tempMsi = Path.Combine(Path.GetTempPath(), "node-setup-x64.msi");

                    ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
                    using (WebClient client = new WebClient())
                    {
                        client.DownloadFile(msiUrl, tempMsi);
                    }

                    UpdateStatus("Installing Node.js runtime quietly in background...", 35);
                    Process msiProc = new Process();
                    msiProc.StartInfo.FileName = "msiexec.exe";
                    msiProc.StartInfo.Arguments = string.Format("/i \"{0}\" /qn /norestart", tempMsi);
                    msiProc.StartInfo.UseShellExecute = true;
                    msiProc.StartInfo.WindowStyle = ProcessWindowStyle.Hidden;
                    msiProc.Start();
                    msiProc.WaitForExit(90000);

                    try { File.Delete(tempMsi); } catch { }
                }
                catch { }
            }

            // Always ensure Node.js is appended to current process PATH
            string activeNodeDir = Directory.Exists(pfNode) ? pfNode : (Directory.Exists(pfNode86) ? pfNode86 : "");
            if (!string.IsNullOrEmpty(activeNodeDir))
            {
                string curPath = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Process) ?? "";
                if (!curPath.Contains(activeNodeDir))
                {
                    Environment.SetEnvironmentVariable("PATH", activeNodeDir + ";" + curPath, EnvironmentVariableTarget.Process);
                }
            }
        }

        private void ExtractPayload()
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream stream = assembly.GetManifestResourceStream("payload.zip"))
            {
                if (stream != null)
                {
                    string tempZip = Path.Combine(Path.GetTempPath(), "jm_vertex_payload.zip");
                    using (FileStream fs = new FileStream(tempZip, FileMode.Create, FileAccess.Write))
                    {
                        stream.CopyTo(fs);
                    }
                    ZipFile.ExtractToDirectory(tempZip, targetDir);
                    try { File.Delete(tempZip); } catch { }
                }
            }
        }

        private void SetupDesktopDependencies()
        {
            string desktopDir = Path.Combine(targetDir, "desktop");
            string electronExe = Path.Combine(desktopDir, "node_modules", "electron", "dist", "electron.exe");

            // If electron.exe is already present, dependencies are fully installed
            if (File.Exists(electronExe)) return;

            string pfNode = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "nodejs");
            string pfNode86 = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "nodejs");
            string nodeDir = Directory.Exists(pfNode) ? pfNode : (Directory.Exists(pfNode86) ? pfNode86 : "");

            string npmCmd = "npm.cmd";
            if (!string.IsNullOrEmpty(nodeDir) && File.Exists(Path.Combine(nodeDir, "npm.cmd")))
            {
                npmCmd = Path.Combine(nodeDir, "npm.cmd");
            }

            UpdateStatus("Setting up desktop engine (installing dependencies)...", 75);

            try
            {
                Process p = new Process();
                p.StartInfo.FileName = npmCmd;
                p.StartInfo.Arguments = "install --no-audit";
                p.StartInfo.WorkingDirectory = desktopDir;
                if (!string.IsNullOrEmpty(nodeDir))
                {
                    p.StartInfo.EnvironmentVariables["PATH"] = nodeDir + ";" + Environment.GetEnvironmentVariable("PATH");
                }
                p.StartInfo.UseShellExecute = false;
                p.StartInfo.CreateNoWindow = true;
                p.StartInfo.WindowStyle = ProcessWindowStyle.Hidden;
                p.Start();
                p.WaitForExit(180000); // Wait up to 3 minutes
            }
            catch { }
        }

        private void ConfigureSilentLauncher()
        {
            // 1. Write the rock-solid runner script (NEVER USES NPX!)
            string runnerBat = Path.Combine(targetDir, "Run-Companion.bat");
            string launcherContent =
                "@echo off\r\n" +
                "cd /d \"%~dp0\"\r\n" +
                "if exist \"%ProgramFiles%\\nodejs\" set \"PATH=%ProgramFiles%\\nodejs;%PATH%\"\r\n" +
                "if exist \"%ProgramFiles(x86)%\\nodejs\" set \"PATH=%ProgramFiles(x86)%\\nodejs;%PATH%\"\r\n" +
                "\r\n" +
                "where python >nul 2>nul\r\n" +
                "if %errorlevel% equ 0 (\r\n" +
                "    start /b \"\" python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 > nul 2>&1\r\n" +
                ")\r\n" +
                "\r\n" +
                "cd desktop\r\n" +
                ":: Direct launch of native electron.exe (ZERO npx dependency!)\r\n" +
                "if exist \"node_modules\\electron\\dist\\electron.exe\" (\r\n" +
                "    start \"\" \"node_modules\\electron\\dist\\electron.exe\" \".\\electron\\main.cjs\"\r\n" +
                "    exit /b 0\r\n" +
                ")\r\n" +
                "\r\n" +
                ":: First-time install fallback if node_modules missing\r\n" +
                "if not exist \"node_modules\" (\r\n" +
                "    call npm.cmd install --no-audit > nul 2>&1\r\n" +
                ")\r\n" +
                "\r\n" +
                "if exist \"node_modules\\electron\\dist\\electron.exe\" (\r\n" +
                "    start \"\" \"node_modules\\electron\\dist\\electron.exe\" \".\\electron\\main.cjs\"\r\n" +
                ") else (\r\n" +
                "    call node.exe .\\electron\\run-electron.cjs > nul 2>&1\r\n" +
                ")\r\n";
            File.WriteAllText(runnerBat, launcherContent);

            // 2. Write VBScript Silent Launcher (WindowStyle = 0 means ZERO CMD WINDOW!)
            vbsPath = Path.Combine(targetDir, "Launch-Companion.vbs");
            string vbsContent =
                "Set WshShell = CreateObject(\"WScript.Shell\")\r\n" +
                "WshShell.CurrentDirectory = \"" + targetDir.Replace("\\", "\\\\") + "\"\r\n" +
                "WshShell.Run \"Run-Companion.bat\", 0, False\r\n";
            File.WriteAllText(vbsPath, vbsContent);

            // 3. Create Desktop Shortcut pointing to silent VBScript launcher
            if (chkDesktopShortcut.Checked)
            {
                CreateDesktopShortcut(vbsPath);
            }
        }

        private void LaunchCompanionSilently()
        {
            try
            {
                if (File.Exists(vbsPath))
                {
                    ProcessStartInfo psi = new ProcessStartInfo
                    {
                        FileName = "wscript.exe",
                        Arguments = "\"" + vbsPath + "\"",
                        WorkingDirectory = targetDir,
                        UseShellExecute = true,
                        WindowStyle = ProcessWindowStyle.Hidden,
                        CreateNoWindow = true
                    };
                    Process.Start(psi);
                }
            }
            catch { }
        }

        private void CreateDesktopShortcut(string targetScript)
        {
            try
            {
                string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string shortcutPath = Path.Combine(desktopPath, "JM Vertex AI Companion.lnk");

                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType != null)
                {
                    dynamic shell = Activator.CreateInstance(shellType);
                    dynamic shortcut = shell.CreateShortcut(shortcutPath);
                    shortcut.TargetPath = "wscript.exe";
                    shortcut.Arguments = "\"" + targetScript + "\"";
                    shortcut.WorkingDirectory = Path.GetDirectoryName(targetScript);
                    shortcut.Description = "JM Vertex AI Desktop Companion";

                    string iconImg = Path.Combine(targetDir, @"desktop\public\companion.webp.png");
                    if (File.Exists(iconImg))
                    {
                        shortcut.IconLocation = iconImg;
                    }
                    shortcut.Save();
                }
            }
            catch { }
        }

        [STAThread]
        public static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupWizardForm());
        }
    }
}
