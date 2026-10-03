// Mouse and keyboard control performed by Naim.app itself.
//
// macOS checks the Accessibility permission of the process that posts the events. Doing it inside Naim.app
// (instead of a separate helper started by Python) means the « Naim » switch in System Settings is the one
// that counts. The Python engine asks for actions through a local bridge (127.0.0.1, secret token).
import AppKit
import ApplicationServices
import Carbon
import Network
import UserNotifications

enum NaimInput {
    static let src = CGEventSource(stateID: .hidSystemState)

    static func trusted(prompt: Bool) -> Bool {
        if prompt {
            let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
            return AXIsProcessTrustedWithOptions(opts)
        }
        return AXIsProcessTrusted()
    }

    static func post(_ e: CGEvent?) {
        e?.post(tap: .cghidEventTap)
        usleep(12000)
    }

    static func mouse(_ type: CGEventType, _ p: CGPoint, _ button: CGMouseButton = .left, clicks: Int64 = 1) {
        let e = CGEvent(mouseEventSource: src, mouseType: type, mouseCursorPosition: p, mouseButton: button)
        e?.setIntegerValueField(.mouseEventClickState, value: clicks)
        post(e)
    }

    static func click(_ x: Double, _ y: Double, _ kind: String) {
        let p = CGPoint(x: x, y: y)
        mouse(.mouseMoved, p)
        if kind == "right" {
            mouse(.rightMouseDown, p, .right); mouse(.rightMouseUp, p, .right)
        } else {
            mouse(.leftMouseDown, p); mouse(.leftMouseUp, p)
            if kind == "double" { mouse(.leftMouseDown, p, clicks: 2); mouse(.leftMouseUp, p, clicks: 2) }
        }
    }

    static func drag(_ a: CGPoint, _ b: CGPoint) {
        mouse(.mouseMoved, a); mouse(.leftMouseDown, a)
        for i in 1...20 {
            let t = Double(i) / 20
            mouse(.leftMouseDragged, CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t))
        }
        mouse(.leftMouseUp, b)
    }

    static func scroll(_ dy: Int32, _ dx: Int32) {
        post(CGEvent(scrollWheelEvent2Source: src, units: .line, wheelCount: 2, wheel1: dy, wheel2: dx, wheel3: 0))
    }

    static func type(_ text: String) {
        for ch in text {
            var u = Array(String(ch).utf16)
            for down in [true, false] {
                let e = CGEvent(keyboardEventSource: src, virtualKey: 0, keyDown: down)
                e?.keyboardSetUnicodeString(stringLength: u.count, unicodeString: &u)
                post(e)
            }
        }
    }

    static let named: [String: CGKeyCode] = [
        "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
        "forwarddelete": 117, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    ]

    // characters of the current keyboard layout (AZERTY, QWERTY…) -> virtual key codes
    static func layoutMap() -> [String: CGKeyCode] {
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

    static func key(_ combo: String) -> Bool {
        var flags: CGEventFlags = []
        var code: CGKeyCode? = nil
        let layout = layoutMap()
        for part in combo.lowercased().split(separator: "+").map(String.init) {
            switch part {
            case "cmd", "command", "⌘": flags.insert(.maskCommand)
            case "shift", "⇧": flags.insert(.maskShift)
            case "alt", "option", "opt", "⌥": flags.insert(.maskAlternate)
            case "ctrl", "control", "⌃": flags.insert(.maskControl)
            case "fn": flags.insert(.maskSecondaryFn)
            default: code = named[part] ?? layout[part]
            }
        }
        guard let k = code else { return false }
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: src, virtualKey: k, keyDown: down)
            e?.flags = flags
            post(e)
        }
        return true
    }

    /// Notification shown by Naim itself (icon Naim, a click opens Naim).
    /// Returns false when macOS refuses: the engine then falls back to a standard notification.
    static func notify(_ title: String, _ body: String) -> Bool {
        let center = UNUserNotificationCenter.current()
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
            guard granted else { sem.signal(); return }
            let c = UNMutableNotificationContent()
            c.title = title
            c.body = body
            c.sound = .default
            center.add(UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil)) { err in
                ok = err == nil
                sem.signal()
            }
        }
        _ = sem.wait(timeout: .now() + 20)  // the first time, macOS asks the user
        return ok
    }

    /// Execute one request from the engine: {"cmd": "click", "args": [...]} -> result dictionary.
    static func run(_ cmd: String, _ a: [String]) -> [String: Any] {
        func num(_ i: Int) -> Double { i < a.count ? Double(a[i]) ?? 0 : 0 }
        if cmd == "perm" {
            let request = a.contains("--request")
            var screen = CGPreflightScreenCaptureAccess()
            if request && !screen { screen = CGRequestScreenCaptureAccess() }  // adds Naim to the Screen Recording list
            return ["accessibility": trusted(prompt: request), "screen": screen]
        }
        if cmd == "notify" {
            let ok = notify(a.first ?? "Naim", a.dropFirst().joined(separator: " "))
            return ok ? ["ok": true] : ["error": "notifications refusées"]
        }
        guard trusted(prompt: false) else { return ["error": "accessibility"] }
        switch cmd {
        case "click": click(num(0), num(1), a.count > 2 ? a[2] : "left")
        case "move": mouse(.mouseMoved, CGPoint(x: num(0), y: num(1)))
        case "drag": drag(CGPoint(x: num(0), y: num(1)), CGPoint(x: num(2), y: num(3)))
        case "scroll": scroll(Int32(num(0)), Int32(num(1)))
        case "type": type(a.joined(separator: " "))
        case "key": if !key(a.first ?? "") { return ["error": "touche inconnue : \(a.first ?? "")"] }
        default: return ["error": "commande inconnue : \(cmd)"]
        }
        return ["ok": true]
    }
}

/// Local bridge: the Python engine (child of this app) sends one JSON line per request; the token is given to it
/// through the environment only, so other programs cannot drive the mouse through Naim.
final class InputBridge {
    let token = UUID().uuidString
    private var listener: NWListener?
    private(set) var port: UInt16 = 0

    func start(ready: @escaping (UInt16) -> Void) {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: .any)
        guard let l = try? NWListener(using: params) else { return }
        listener = l
        l.stateUpdateHandler = { [weak self] state in
            if case .ready = state, let p = l.port?.rawValue {
                self?.port = p
                ready(p)
            }
        }
        l.newConnectionHandler = { [weak self] conn in
            conn.start(queue: .global())
            self?.read(conn, Data())
        }
        l.start(queue: .main)
    }

    private func read(_ conn: NWConnection, _ buffer: Data) {
        conn.receive(minimumIncompleteLength: 1, maximumLength: 1 << 20) { [weak self] data, _, done, error in
            var buf = buffer
            if let d = data { buf.append(d) }
            if let nl = buf.firstIndex(of: 0x0A) {
                self?.answer(conn, buf[..<nl])
            } else if done || error != nil || buf.count > (1 << 20) {
                conn.cancel()
            } else {
                self?.read(conn, buf)
            }
        }
    }

    private func answer(_ conn: NWConnection, _ line: Data) {
        var result: [String: Any]
        if let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any],
           obj["token"] as? String == token, let cmd = obj["cmd"] as? String {
            let args = (obj["args"] as? [Any] ?? []).map { "\($0)" }
            result = NaimInput.run(cmd, args)
        } else {
            result = ["error": "requête refusée"]
        }
        var out = (try? JSONSerialization.data(withJSONObject: result)) ?? Data("{}".utf8)
        out.append(0x0A)
        conn.send(content: out, completion: .contentProcessed { _ in conn.cancel() })
    }
}
