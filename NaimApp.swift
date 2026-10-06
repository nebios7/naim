// Naim.app — native macOS shell of Naim.
//
// A real AppKit app (window, menus, Dock, « À propos », permissions) that shows Naim's web interface in a
// WKWebView. The engine (agent, tools, server, scheduler) runs in Python as a child process
// (`naim.py --server`), so macOS attributes Accessibility / Screen Recording / Automation to Naim.app.
//
// Keep this file stable: rebuilding the app changes its signature and macOS may forget the permissions.
import AppKit
import WebKit

let naimVersion = "3.0"
let home = FileManager.default.homeDirectoryForCurrentUser.path
let dataDir = ProcessInfo.processInfo.environment["NAIM_DATA"] ?? "\(home)/Library/Application Support/Naim"
let port = ProcessInfo.processInfo.environment["NAIM_PORT"] ?? "8765"
let baseURL = URL(string: "http://127.0.0.1:\(port)/")!
let logPath = "\(home)/Library/Logs/Naim.log"

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, NSWindowDelegate {
    var window: NSWindow!
    var web: WKWebView!
    let dictation = NaimDictation()  // the composer's microphone
    var engine: Process?
    let bridge = InputBridge()
    var readyTimer: Timer?
    var started = Date()

    // MARK: launch
    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenus()
        buildWindow()
        showLoading("Démarrage de Naim…")
        NSApp.activate(ignoringOtherApps: true)
        // clicks and typing are done by this app (Accessibility is checked for Naim.app): start the bridge first
        var launched = false
        bridge.start { [weak self] _ in
            guard let self = self, !launched else { return }
            launched = true
            self.startEngine()
            self.waitUntilReady()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in  // bridge unavailable: start anyway
            guard let self = self, !launched else { return }
            launched = true
            self.startEngine()
            self.waitUntilReady()
        }
    }

    func buildWindow() {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .default()
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = true
        cfg.userContentController.add(dictation, name: "naimDictation")
        web = WKWebView(frame: .zero, configuration: cfg)
        dictation.web = web
        web.uiDelegate = self
        web.navigationDelegate = self
        web.allowsMagnification = false
        web.allowsBackForwardNavigationGestures = false
        if #available(macOS 13.3, *) { web.isInspectable = true }  // Safari › Développement, for debugging
        web.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1240, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Naim"
        window.backgroundColor = NSColor(red: 0.086, green: 0.086, blue: 0.082, alpha: 1)
        window.minSize = NSSize(width: 720, height: 520)
        window.contentView = web
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.center()
        window.setFrameAutosaveName("NaimMainWindow")
        window.makeKeyAndOrderFront(nil)
    }

    func showLoading(_ text: String, detail: String = "") {
        let busy = detail.isEmpty  // starting: a moving bar; a problem: the details instead
        let html = """
        <html><head><meta charset="utf-8"><meta name="color-scheme" content="dark light"><style>
        :root { --bg:#161615; --text:#e8e6e1; --muted:#9a978f; --line:#2c2b29; }
        @media (prefers-color-scheme: light) { :root { --bg:#faf9f5; --text:#1f1e1d; --muted:#73726c; --line:#e3e1d8; } }
        body { margin:0; height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center;
               background:var(--bg); color:var(--text); font:14px -apple-system,system-ui; -webkit-user-select:text; }
        .w { font-family: ui-serif,"New York","Iowan Old Style",Georgia,serif; font-size:48px; font-weight:500; letter-spacing:-1px; }
        .t { margin-top:10px; color:var(--muted); }
        .bar { margin-top:22px; width:160px; height:2px; border-radius:2px; background:var(--line); overflow:hidden; }
        .bar i { display:block; width:40%; height:100%; background:var(--text); opacity:.7; animation: m 1.4s ease-in-out infinite; }
        @keyframes m { 0% { transform:translateX(-100%); } 100% { transform:translateX(250%); } }
        pre { margin-top:18px; max-width:80%; white-space:pre-wrap; color:var(--muted); font-size:12px; }
        </style></head><body><div class="w">Naim</div><div class="t">\(text)</div>
        \(busy ? "<div class=\"bar\"><i></i></div>" : "<pre>\(detail)</pre>")</body></html>
        """
        web.loadHTMLString(html, baseURL: nil)
    }

    // MARK: engine (Python)
    func engineReachable() -> Bool {
        var req = URLRequest(url: baseURL.appendingPathComponent("api/computer"))
        req.timeoutInterval = 1
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            ok = (resp as? HTTPURLResponse)?.statusCode == 200
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 1.5)
        return ok
    }

    func startEngine() {
        if engineReachable() { return }  // another Naim (naim --web) already serves: share it
        let python = "\(dataDir)/venv/bin/python"
        let script = "\(dataDir)/app/naim.py"
        guard FileManager.default.fileExists(atPath: python), FileManager.default.fileExists(atPath: script) else {
            showLoading("Naim n'est pas installé correctement", detail: "Introuvable : \(python)\nou \(script)\n\nRelance : bash install.sh")
            return
        }
        if !FileManager.default.fileExists(atPath: logPath) { FileManager.default.createFile(atPath: logPath, contents: nil) }
        let log = FileHandle(forWritingAtPath: logPath)
        log?.seekToEndOfFile()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: python)
        p.arguments = [script, "--server"]
        p.currentDirectoryURL = URL(fileURLWithPath: "\(dataDir)/app")
        var env = ProcessInfo.processInfo.environment
        env["NAIM_PORT"] = port
        if bridge.port > 0 { env["NAIM_BRIDGE"] = "\(bridge.port):\(bridge.token)" }
        env["PYTHONUNBUFFERED"] = "1"
        // Finder gives apps a minimal PATH: add Homebrew so llama-server, git, npm, uv… are found
        env["PATH"] = "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        env["LANG"] = env["LANG"] ?? "fr_FR.UTF-8"
        p.environment = env
        p.standardOutput = log
        p.standardError = log
        p.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                guard let self = self, self.engine === proc, !self.quitting else { return }
                self.engine = nil
                self.showLoading("Le moteur de Naim s'est arrêté", detail: self.logTail() + "\n\nMenu Naim › Redémarrer le moteur")
            }
        }
        do {
            try p.run()
            engine = p
        } catch {
            showLoading("Impossible de démarrer le moteur de Naim", detail: "\(error)")
        }
    }

    func waitUntilReady() {
        started = Date()
        readyTimer?.invalidate()
        readyTimer = Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { [weak self] t in
            guard let self = self else { return t.invalidate() }
            DispatchQueue.global().async {
                let ok = self.engineReachable()
                DispatchQueue.main.async {
                    if ok {
                        t.invalidate()
                        self.web.load(URLRequest(url: baseURL))
                    } else if Date().timeIntervalSince(self.started) > 60 {
                        t.invalidate()
                        self.showLoading("Naim ne répond pas", detail: self.logTail())
                    }
                }
            }
        }
    }

    func logTail() -> String {
        guard let text = try? String(contentsOfFile: logPath, encoding: .utf8) else { return "" }
        return text.split(separator: "\n", omittingEmptySubsequences: false).suffix(25).joined(separator: "\n")
            .replacingOccurrences(of: "<", with: "&lt;")
    }

    var quitting = false

    func stopEngine() {
        guard let p = engine, p.isRunning else { return }
        quitting = true
        p.terminate()  // SIGTERM: Python stops background programs, MCP servers and llama-server
        let deadline = Date().addingTimeInterval(6)
        while p.isRunning && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.1)) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
    }

    @objc func restartEngine(_ sender: Any?) {
        stopEngine()
        quitting = false
        showLoading("Redémarrage du moteur…")
        startEngine()
        waitUntilReady()
    }

    // MARK: app lifecycle
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }  // scheduled tasks keep running

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }

    func applicationWillTerminate(_ notification: Notification) { stopEngine() }

    // MARK: web view behaviour
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = action.request.url, let host = url.host, host != "127.0.0.1", host != "localhost",
           url.scheme == "http" || url.scheme == "https" {
            NSWorkspace.shared.open(url)  // external links open in the default browser
            return decisionHandler(.cancel)
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }  // target=_blank
        return nil
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert()
        a.messageText = message
        a.addButton(withTitle: "OK")
        a.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = NSAlert()
        a.messageText = message
        a.addButton(withTitle: "OK")
        a.addButton(withTitle: "Annuler")
        a.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert()
        a.messageText = prompt
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
        field.stringValue = defaultText ?? ""
        a.accessoryView = field
        a.addButton(withTitle: "OK")
        a.addButton(withTitle: "Annuler")
        a.window.initialFirstResponder = field
        a.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }

    // MARK: menus
    @objc func command(_ sender: NSMenuItem) {
        guard let name = sender.representedObject as? String else { return }
        window.makeKeyAndOrderFront(nil)
        web.evaluateJavaScript("window.naimCmd && naimCmd('\(name)')", completionHandler: nil)
    }

    @objc func showAbout(_ sender: Any?) {
        NSApp.orderFrontStandardAboutPanel(options: [
            .applicationName: "Naim",
            .applicationVersion: "Version \(naimVersion)",
            .version: "",
            .credits: NSAttributedString(string: "Agent autonome local, successeur de Mimo.",
                                         attributes: [.foregroundColor: NSColor.secondaryLabelColor,
                                                      .font: NSFont.systemFont(ofSize: 11)]),
            NSApplication.AboutPanelOptionKey(rawValue: "Copyright"): "© ABDESSEMED Mohamed",
        ])
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func askAccessibility(_ sender: Any?) {
        var screen = CGPreflightScreenCaptureAccess()
        if !screen { screen = CGRequestScreenCaptureAccess() }  // adds « Naim » to the Screen Recording list
        let ax = NaimInput.trusted(prompt: true)                // adds « Naim » to the Accessibility list
        let a = NSAlert()
        a.messageText = screen && ax ? "Naim a toutes les autorisations ✓" : "Autorisations de Naim"
        a.informativeText = "\(screen ? "✓" : "✗") Enregistrement de l'écran\n\(ax ? "✓" : "✗") Accessibilité (clics et frappe)"
            + (screen && ax ? "" : "\n\nActive « Naim » dans les listes qui vont s'ouvrir, puis quitte (⌘Q) et relance Naim.")
        a.runModal()
        if !screen, let u = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture") {
            NSWorkspace.shared.open(u)
        } else if !ax, let u = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(u)
        }
    }

    @objc func openLog(_ sender: Any?) { NSWorkspace.shared.open(URL(fileURLWithPath: logPath)) }
    @objc func openData(_ sender: Any?) { NSWorkspace.shared.open(URL(fileURLWithPath: "\(home)/.naim")) }
    @objc func reloadPage(_ sender: Any?) { web.reload() }
    @objc func showMainWindow(_ sender: Any?) { window.makeKeyAndOrderFront(nil) }

    func item(_ title: String, _ cmd: String, _ key: String = "", _ mods: NSEvent.ModifierFlags = [.command]) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: #selector(command(_:)), keyEquivalent: key)
        i.keyEquivalentModifierMask = mods
        i.representedObject = cmd
        i.target = self
        return i
    }

    func action(_ title: String, _ sel: Selector, _ key: String = "", _ mods: NSEvent.ModifierFlags = [.command],
                target: AnyObject? = nil) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: sel, keyEquivalent: key)
        i.keyEquivalentModifierMask = mods
        i.target = target
        return i
    }

    func buildMenus() {
        let main = NSMenu()
        func add(_ title: String, _ items: [NSMenuItem]) -> NSMenu {
            let top = NSMenuItem()
            let m = NSMenu(title: title)
            items.forEach(m.addItem)
            top.submenu = m
            main.addItem(top)
            return m
        }
        let sep = { NSMenuItem.separator() }

        _ = add("Naim", [
            action("À propos de Naim", #selector(showAbout(_:)), target: self), sep(),
            item("Personnaliser…", "settings", ","),
            item("Modèles…", "models"),
            item("Raccourcis clavier", "shortcuts", "/"), sep(),
            action("Redémarrer le moteur", #selector(restartEngine(_:)), target: self),
            action("Autoriser le contrôle de l'écran…", #selector(askAccessibility(_:)), target: self),
            action("Ouvrir le dossier ~/.naim", #selector(openData(_:)), target: self), sep(),
            action("Masquer Naim", #selector(NSApplication.hide(_:)), "h"),
            action("Masquer les autres", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            action("Tout afficher", #selector(NSApplication.unhideAllApplications(_:))), sep(),
            action("Quitter Naim", #selector(NSApplication.terminate(_:)), "q"),
        ])
        _ = add("Fichier", [
            item("Nouvelle conversation", "new", "n"),
            item("Palette de commandes", "palette", "k"), sep(),
            item("Exporter la conversation", "export", "e", [.command, .shift]),
            item("Ouvrir le projet dans le Finder", "reveal"), sep(),
            action("Fermer la fenêtre", #selector(NSWindow.performClose(_:)), "w"),
        ])
        _ = add("Édition", [
            action("Annuler", Selector(("undo:")), "z"),
            action("Rétablir", Selector(("redo:")), "z", [.command, .shift]), sep(),
            action("Couper", #selector(NSText.cut(_:)), "x"),
            action("Copier", #selector(NSText.copy(_:)), "c"),
            action("Coller", #selector(NSText.paste(_:)), "v"),
            action("Tout sélectionner", #selector(NSText.selectAll(_:)), "a"), sep(),
            item("Copier la dernière réponse", "copyLast", "c", [.command, .shift]),
        ])
        _ = add("Présentation", [
            item("Zoom avant", "zoomIn", "+"),
            item("Zoom arrière", "zoomOut", "-"),
            item("Taille réelle", "zoomReset", "0"), sep(),
            item("Barre latérale", "sidebar", "b"),
            item("Terminal", "terminal", "j"),
            item("Fichiers du projet", "files", "f", [.command, .shift]),
            item("Artéfacts", "artifacts"),
            item("Planifier", "schedules"), sep(),
            item("Mode Chat / Agent", "toggleMode", "a", [.command, .shift]),
            item("Raisonnement", "toggleThink", "r", [.command, .shift]), sep(),
            action("Actualiser", #selector(reloadPage(_:)), "r", target: self),
            action("Plein écran", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])
        let win = add("Fenêtre", [
            action("Réduire", #selector(NSWindow.performMiniaturize(_:)), "m"),
            action("Zoom", #selector(NSWindow.performZoom(_:))), sep(),
            action("Naim", #selector(showMainWindow(_:)), "0", [.command, .option], target: self),
        ])
        NSApp.windowsMenu = win
        let help = add("Aide", [
            action("Journal de Naim", #selector(openLog(_:)), target: self),
        ])
        NSApp.helpMenu = help
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
signal(SIGTERM, SIG_IGN)
let term = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
term.setEventHandler { NSApp.terminate(nil) }
term.resume()
app.run()
