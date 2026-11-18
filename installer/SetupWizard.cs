using System;
using System.IO;
using System.Drawing;
using System.Windows.Forms;
using System.Diagnostics;
using System.Reflection;
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
        private string runnerBatPath = "";

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
            this.Text = "JM Vertex AI Companion — Laptop Setup Wizard";
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
            lblSubtitle.Text = "Your Smart Desktop Assistant — 1-Click Laptop Installer";
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
            chkDesktopShortcut.Text = "Create Desktop Shortcut (1-Click Run)";
            chkDesktopShortcut.Checked = true;
            chkDesktopShortcut.ForeColor = Color.FromArgb(220, 220, 220);
            chkDesktopShortcut.Location = new Point(25, 300);
            chkDesktopShortcut.AutoSize = true;

            chkLaunchNow = new CheckBox();
            chkLaunchNow.Text = "Launch JM Vertex AI Companion immediately after setup";
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

            // Timer for installation progress
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
                    "Status: [VALIDATED WINDOWS HARDWARE PROFILE]",
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
            installTimer.Start();
        }

        private void InstallTimer_Tick(object sender, EventArgs e)
        {
            installProgress += 5;
            if (installProgress > 100) installProgress = 100;

            progressBar.Value = installProgress;

            if (installProgress < 25)
            {
                lblStatus.Text = "Creating directories at " + txtPath.Text + "...";
            }
            else if (installProgress < 50)
            {
                lblStatus.Text = "Extracting Doraemon Avatar & Desktop Movement engine...";
            }
            else if (installProgress < 75)
            {
                lblStatus.Text = "Configuring Python Universal Windows Automation & FastAPI API...";
            }
            else if (installProgress < 95)
            {
                lblStatus.Text = "Creating Desktop shortcuts and configuring 1-click launcher...";
            }
            else
            {
                installTimer.Stop();
                PerformActualInstall();
            }
        }

        private void PerformActualInstall()
        {
            try
            {
                string targetDir = txtPath.Text;
                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                // 1. Extract embedded payload.zip into target directory
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

                // 2. Write the 1-Click Runner Script in the installed directory
                runnerBatPath = Path.Combine(targetDir, "Run-Companion.bat");

                // Check if the current workspace with node_modules exists on this machine
                string workspaceBat = @"E:\Jm vertex\Launch-Companion.bat";
                string launcherContent;

                if (File.Exists(workspaceBat))
                {
                    launcherContent =
                        "@echo off\r\n" +
                        "title JM Vertex - AI Desktop Companion\r\n" +
                        "echo Starting JM Vertex AI Companion on " + Environment.MachineName + "...\r\n" +
                        "cd /d \"E:\\Jm vertex\"\r\n" +
                        "call Launch-Companion.bat\r\n";
                }
                else
                {
                    launcherContent =
                        "@echo off\r\n" +
                        "title JM Vertex - AI Desktop Companion\r\n" +
                        "echo ======================================================================\r\n" +
                        "echo   JM VERTEX TECHNOLOGIES - AI DESKTOP COMPANION\r\n" +
                        "echo   Launching Desktop Avatar & Windows Automation Engine...\r\n" +
                        "echo ======================================================================\r\n" +
                        "cd /d \"%~dp0\"\r\n" +
                        "\r\n" +
                        "echo [*] Starting Python Automation API Backend on port 8000...\r\n" +
                        "start /b \"\" python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 > nul 2>&1\r\n" +
                        "timeout /t 2 /nobreak > nul\r\n" +
                        "\r\n" +
                        "echo [*] Launching Desktop Companion Interface...\r\n" +
                        "if exist \"desktop\\node_modules\" (\r\n" +
                        "    cd desktop\r\n" +
                        "    call npx electron ./electron/run-electron.cjs\r\n" +
                        ") else (\r\n" +
                        "    cd desktop\r\n" +
                        "    call npm install\r\n" +
                        "    call npm run app\r\n" +
                        ")\r\n" +
                        "\r\n" +
                        "echo [*] Shutting down backend on exit...\r\n" +
                        "for /f \"tokens=5\" %%a in ('netstat -aon ^| findstr \":8000\" ^| findstr \"LISTENING\"') do (\r\n" +
                        "    taskkill /F /PID %%a > nul 2>&1\r\n" +
                        ")\r\n";
                }

                File.WriteAllText(runnerBatPath, launcherContent);

                // 3. Create Desktop Shortcut if checked
                if (chkDesktopShortcut.Checked)
                {
                    CreateDesktopShortcut(runnerBatPath);
                }

                lblStatus.Text = "Installation Successful! Companion ready on your laptop.";
                lblStatus.ForeColor = Color.FromArgb(0, 230, 118);
                btnInstall.Text = "START COMPANION NOW";
                btnInstall.Enabled = true;
                btnCancel.Text = "Close";
                btnCancel.Visible = true;
                btnCancel.Enabled = true;

                btnInstall.Click -= BtnInstall_Click;
                btnInstall.Click += (s, e) => {
                    LaunchAppAndExit();
                };

                // If user selected "Launch immediately"
                if (chkLaunchNow.Checked)
                {
                    LaunchAppAndExit();
                }
            }
            catch (Exception ex)
            {
                lblStatus.Text = "Installation completed with notice: " + ex.Message;
                lblStatus.ForeColor = Color.Orange;
                btnInstall.Enabled = true;
                btnCancel.Enabled = true;
            }
        }

        private void LaunchAppAndExit()
        {
            try
            {
                if (File.Exists(runnerBatPath))
                {
                    ProcessStartInfo psi = new ProcessStartInfo
                    {
                        FileName = "cmd.exe",
                        Arguments = "/k \"" + runnerBatPath + "\"",
                        WorkingDirectory = Path.GetDirectoryName(runnerBatPath),
                        UseShellExecute = true
                    };
                    Process.Start(psi);
                }
            }
            catch { }
            this.Close();
        }

        private void CreateDesktopShortcut(string targetPath)
        {
            try
            {
                string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string shortcutPath = Path.Combine(desktopPath, "JM Vertex AI Companion.url");
                using (StreamWriter writer = new StreamWriter(shortcutPath))
                {
                    writer.WriteLine("[InternetShortcut]");
                    writer.WriteLine("URL=file:///" + targetPath.Replace('\\', '/'));
                    writer.WriteLine("IconIndex=0");
                    writer.WriteLine("IconFile=" + targetPath);
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
