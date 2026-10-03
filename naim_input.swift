// naim-input: small native helper for Naim's computer-use tools.
// OCR (Vision), mouse and keyboard events (CGEvent), window list and permission checks.
// Usage:
//   naim-input perm [--request]            -> {"screen": bool, "accessibility": bool}
//   naim-input screen                      -> {"width": pts, "height": pts, "scale": s}
//   naim-input ocr <png>                   -> [{"text", "x", "y", "w", "h"}] in image pixels, top-left origin
//   naim-input windows [owner]             -> [{"id", "owner", "name", "x", "y", "w", "h"}]
//   naim-input appwin <app name>           -> largest window of that app, or null
//   naim-input pdf <file> [max pages]      -> {"pages": n, "text": [...]} ; scanned pages are read with OCR
//   naim-input click <x> <y> [left|right|double]
//   naim-input move <x> <y>
//   naim-input drag <x1> <y1> <x2> <y2>
//   naim-input scroll <dy> [dx]
//   naim-input type <text>
//   naim-input key <combo>                 e.g. cmd+s, cmd+shift+h, return, escape, tab, up
import AppKit
import ApplicationServices
import Carbon
import Foundation
import PDFKit
import Vision

func out(_ obj: Any) {
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [.fragmentsAllowed])
    print(String(data: data, encoding: .utf8)!)
}

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(1)
}

let args = Array(CommandLine.arguments.dropFirst())
guard let cmd = args.first else { fail("usage: naim-input <command> ...") }
func num(_ i: Int) -> Double {
    guard i < args.count, let v = Double(args[i]) else { fail("missing number argument #\(i)") }
    return v
}

let src = CGEventSource(stateID: .hidSystemState)

func post(_ e: CGEvent?) {
    e?.post(tap: .cghidEventTap)
    usleep(12000)
}

func mouse(_ type: CGEventType, _ p: CGPoint, _ button: CGMouseButton = .left, clicks: Int64 = 1) {
    let e = CGEvent(mouseEventSource: src, mouseType: type, mouseCursorPosition: p, mouseButton: button)
    e?.setIntegerValueField(.mouseEventClickState, value: clicks)
    post(e)
}

// Map characters of the current keyboard layout (AZERTY, QWERTY...) to virtual key codes.
func layoutMap() -> [String: CGKeyCode] {
    var map: [String: CGKeyCode] = [:]
    guard let source = TISCopyCurrentKeyboardLayoutInputSource()?.takeRetainedValue(),
          let ptr = TISGetInputSourceProperty(source, kTISPropertyUnicodeKeyLayoutData) else { return map }
    let data = Unmanaged<CFData>.fromOpaque(ptr).takeUnretainedValue() as Data
    data.withUnsafeBytes { raw in
        guard let layout = raw.baseAddress?.assumingMemoryBound(to: UCKeyboardLayout.self) else { return }
        for code in 0..<128 {
            var dead: UInt32 = 0
            var chars = [UniChar](repeating: 0, count: 4)
            var len = 0
            let st = UCKeyTranslate(layout, UInt16(code), UInt16(kUCKeyActionDown), 0, UInt32(LMGetKbdType()),
                                    OptionBits(kUCKeyTranslateNoDeadKeysBit), &dead, 4, &len, &chars)
            if st == noErr, len > 0 {
                let s = String(utf16CodeUnits: chars, count: len).lowercased()
                if map[s] == nil { map[s] = CGKeyCode(code) }
            }
        }
    }
    return map
}

let NAMED: [String: CGKeyCode] = [
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "forwarddelete": 117, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
]

switch cmd {
case "perm":
    var ax = AXIsProcessTrusted()
    var screen = CGPreflightScreenCaptureAccess()
    if args.contains("--request") {
        if !screen { screen = CGRequestScreenCaptureAccess() }
        if !ax {
            let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
            ax = AXIsProcessTrustedWithOptions(opts)
        }
    }
    out(["screen": screen, "accessibility": ax])

case "screen":
    let s = NSScreen.main ?? NSScreen.screens[0]
    out(["width": s.frame.width, "height": s.frame.height, "scale": s.backingScaleFactor])

case "ocr":
    guard args.count > 1, let img = NSImage(contentsOfFile: args[1]),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { fail("cannot read image") }
    let W = Double(cg.width), H = Double(cg.height)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    req.recognitionLanguages = ["fr-FR", "en-US"]
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    var items: [[String: Any]] = []
    for o in req.results ?? [] {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox  // normalised, bottom-left origin
        items.append(["text": c.string, "x": Int(b.midX * W), "y": Int((1 - b.midY) * H),
                      "w": Int(b.width * W), "h": Int(b.height * H)])
    }
    out(items)

case "windows":
    let owner = args.count > 1 ? args[1].lowercased() : nil
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    var res: [[String: Any]] = []
    for w in list {
        let o = (w[kCGWindowOwnerName as String] as? String) ?? ""
        if let owner = owner, !o.lowercased().contains(owner) { continue }
        guard (w[kCGWindowLayer as String] as? Int) == 0,
              let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
        res.append(["id": w[kCGWindowNumber as String] as? Int ?? 0, "owner": o,
                    "name": (w[kCGWindowName as String] as? String) ?? "",
                    "x": b["X"] ?? 0, "y": b["Y"] ?? 0, "w": b["Width"] ?? 0, "h": b["Height"] ?? 0])
    }
    out(res)

case "appwin":
    // largest on-screen window of a running app, matched by name ("Calculator", "Calculatrice") or bundle id
    guard args.count > 1 else { fail("missing app name") }
    let want = args[1].lowercased()
    let apps = NSWorkspace.shared.runningApplications.filter { a in
        let names = [a.localizedName, a.bundleURL?.deletingPathExtension().lastPathComponent, a.bundleIdentifier]
        return names.contains { ($0 ?? "").lowercased() == want }
    }
    let pids = Set(apps.map { Int($0.processIdentifier) })
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    var best: [String: Any]? = nil
    var area = 0.0
    for w in list {
        guard let pid = w[kCGWindowOwnerPID as String] as? Int, pids.contains(pid),
              (w[kCGWindowLayer as String] as? Int) == 0,
              let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
        let a = (b["Width"] ?? 0) * (b["Height"] ?? 0)
        if a > area && (b["Width"] ?? 0) > 80 {
            area = a
            best = ["id": w[kCGWindowNumber as String] as? Int ?? 0, "owner": (w[kCGWindowOwnerName as String] as? String) ?? "",
                    "name": (w[kCGWindowName as String] as? String) ?? "",
                    "x": b["X"] ?? 0, "y": b["Y"] ?? 0, "w": b["Width"] ?? 0, "h": b["Height"] ?? 0]
        }
    }
    out(best ?? NSNull())

case "pdf":
    guard args.count > 1, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else { fail("cannot open PDF") }
    let maxPages = args.count > 2 ? Int(args[2]) ?? 60 : 60
    var texts: [String] = []
    for i in 0..<min(doc.pageCount, maxPages) {
        guard let page = doc.page(at: i) else { texts.append(""); continue }
        var t = page.string ?? ""
        if t.trimmingCharacters(in: .whitespacesAndNewlines).count < 20 {
            // scanned page: render it and read it with OCR
            let box = page.bounds(for: .mediaBox)
            let scale = 2.0
            let img = page.thumbnail(of: NSSize(width: box.width * scale, height: box.height * scale), for: .mediaBox)
            if let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) {
                let req = VNRecognizeTextRequest()
                req.recognitionLevel = .accurate
                req.recognitionLanguages = ["fr-FR", "en-US"]
                try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
                let lines = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }
                if !lines.isEmpty { t = lines.joined(separator: "\n") }
            }
        }
        texts.append(t)
    }
    out(["pages": doc.pageCount, "text": texts])

case "click":
    let p = CGPoint(x: num(1), y: num(2))
    let kind = args.count > 3 ? args[3] : "left"
    mouse(.mouseMoved, p)
    if kind == "right" {
        mouse(.rightMouseDown, p, .right); mouse(.rightMouseUp, p, .right)
    } else {
        mouse(.leftMouseDown, p); mouse(.leftMouseUp, p)
        if kind == "double" { mouse(.leftMouseDown, p, clicks: 2); mouse(.leftMouseUp, p, clicks: 2) }
    }
    out(["ok": true])

case "move":
    mouse(.mouseMoved, CGPoint(x: num(1), y: num(2)))
    out(["ok": true])

case "drag":
    let a = CGPoint(x: num(1), y: num(2)), b = CGPoint(x: num(3), y: num(4))
    mouse(.mouseMoved, a); mouse(.leftMouseDown, a)
    for i in 1...20 {
        let t = Double(i) / 20
        mouse(.leftMouseDragged, CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t))
    }
    mouse(.leftMouseUp, b)
    out(["ok": true])

case "scroll":
    let dy = Int32(num(1)), dx = args.count > 2 ? Int32(num(2)) : 0
    post(CGEvent(scrollWheelEvent2Source: src, units: .line, wheelCount: 2, wheel1: dy, wheel2: dx, wheel3: 0))
    out(["ok": true])

case "type":
    guard args.count > 1 else { fail("missing text") }
    for ch in args[1...].joined(separator: " ") {
        var u = Array(String(ch).utf16)
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: src, virtualKey: 0, keyDown: down)
            e?.keyboardSetUnicodeString(stringLength: u.count, unicodeString: &u)
            post(e)
        }
    }
    out(["ok": true])

case "key":
    guard args.count > 1 else { fail("missing key") }
    var flags: CGEventFlags = []
    var code: CGKeyCode? = nil
    let layout = layoutMap()
    for part in args[1].lowercased().split(separator: "+").map(String.init) {
        switch part {
        case "cmd", "command", "⌘": flags.insert(.maskCommand)
        case "shift", "⇧": flags.insert(.maskShift)
        case "alt", "option", "opt", "⌥": flags.insert(.maskAlternate)
        case "ctrl", "control", "⌃": flags.insert(.maskControl)
        case "fn": flags.insert(.maskSecondaryFn)
        default: code = NAMED[part] ?? layout[part]
        }
    }
    guard let k = code else { fail("unknown key in \(args[1])") }
    for down in [true, false] {
        let e = CGEvent(keyboardEventSource: src, virtualKey: k, keyDown: down)
        e?.flags = flags
        post(e)
    }
    out(["ok": true])

default:
    fail("unknown command \(cmd)")
}
