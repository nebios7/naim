// Naim in the menu bar: an icon at the top of the screen that opens a floating input bar (bottom of the
// screen, Naim's dark theme). Enter sends the message to Naim's window, in a new or in the current conversation.
import AppKit
import WebKit

final class QuickPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

final class NaimQuick: NSObject, NSTextFieldDelegate, NSWindowDelegate {
    var statusItem: NSStatusItem!
    var panel: QuickPanel!
    var field: NSTextField!
    var target: NSPopUpButton!
    var send: NSButton!
    var deliver: ((String, Bool) -> Void)?   // (text, new conversation)
    var openMain: (() -> Void)?

    // Naim's « Sombre » palette
    let bg = NSColor(srgbRed: 0.106, green: 0.106, blue: 0.102, alpha: 0.97)      // #1b1b1a
    let line = NSColor(srgbRed: 0.192, green: 0.192, blue: 0.188, alpha: 1)       // #313130
    let text = NSColor(srgbRed: 0.980, green: 0.976, blue: 0.961, alpha: 1)       // #faf9f5
    let muted = NSColor(srgbRed: 0.659, green: 0.651, blue: 0.620, alpha: 1)      // #a8a69e

    func install() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let b = statusItem.button {
            b.image = NaimQuick.mark(size: 18, template: true)
            b.toolTip = "Naim — demander quelque chose (clic droit : menu)"
            b.target = self
            b.action = #selector(clicked(_:))
            b.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
        buildPanel()
    }

    // the Naim mark: a serif « N » (the app icon's face)
    static func mark(size: CGFloat, template: Bool, color: NSColor = .black) -> NSImage {
        let img = NSImage(size: NSSize(width: size, height: size), flipped: false) { r in
            var font = NSFont.systemFont(ofSize: size * 0.86, weight: .semibold)
            if let d = font.fontDescriptor.withDesign(.serif), let f = NSFont(descriptor: d, size: size * 0.86) { font = f }
            let s = NSAttributedString(string: "N", attributes: [.font: font, .foregroundColor: color])
            let z = s.size()
            s.draw(at: NSPoint(x: (r.width - z.width) / 2, y: (r.height - z.height) / 2 + size * 0.04))
            // the thin line under the name, as on the app icon
            color.withAlphaComponent(0.8).setFill()
            NSBezierPath(roundedRect: NSRect(x: r.width * 0.28, y: r.height * 0.06, width: r.width * 0.44, height: max(1.2, size * 0.07)),
                         xRadius: 1, yRadius: 1).fill()
            return true
        }
        img.isTemplate = template
        return img
    }

    @objc func clicked(_ sender: NSStatusBarButton) {
        if NSApp.currentEvent?.type == .rightMouseUp {
            let m = NSMenu()
            m.addItem(withTitle: "Demander à Naim…", action: #selector(toggle), keyEquivalent: "").target = self
            m.addItem(withTitle: "Ouvrir la fenêtre de Naim", action: #selector(showMain), keyEquivalent: "").target = self
            m.addItem(.separator())
            m.addItem(withTitle: "Quitter Naim", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "")
            statusItem.menu = m
            statusItem.button?.performClick(nil)
            statusItem.menu = nil
        } else {
            toggle()
        }
    }

    @objc func showMain() { openMain?() }

    func buildPanel() {
        let w: CGFloat = 680, h: CGFloat = 60
        panel = QuickPanel(contentRect: NSRect(x: 0, y: 0, width: w, height: h),
                           styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = true
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.delegate = self

        let box = NSView(frame: NSRect(x: 0, y: 0, width: w, height: h))
        box.wantsLayer = true
        box.layer?.backgroundColor = bg.cgColor
        box.layer?.cornerRadius = 16
        box.layer?.borderWidth = 1
        box.layer?.borderColor = line.cgColor
        box.appearance = NSAppearance(named: .darkAqua)
        panel.contentView = box

        let logo = NSImageView(frame: NSRect(x: 16, y: (h - 22) / 2, width: 22, height: 22))
        logo.image = NaimQuick.mark(size: 22, template: false, color: text)
        box.addSubview(logo)

        field = NSTextField(frame: NSRect(x: 48, y: (h - 24) / 2, width: w - 48 - 230, height: 24))
        field.isBordered = false
        field.drawsBackground = false
        field.focusRingType = .none
        field.font = .systemFont(ofSize: 16)
        field.textColor = text
        field.placeholderAttributedString = NSAttributedString(string: "Comment puis-je t'aider ?",
            attributes: [.foregroundColor: muted, .font: NSFont.systemFont(ofSize: 16)])
        field.delegate = self
        field.cell?.usesSingleLineMode = true
        field.cell?.lineBreakMode = .byTruncatingHead
        box.addSubview(field)

        target = NSPopUpButton(frame: NSRect(x: w - 220, y: (h - 26) / 2, width: 170, height: 26), pullsDown: false)
        target.addItems(withTitles: ["Nouvelle conversation", "Conversation en cours"])
        target.isBordered = false
        target.font = .systemFont(ofSize: 13)
        (target.cell as? NSPopUpButtonCell)?.arrowPosition = .arrowAtBottom
        target.contentTintColor = muted
        box.addSubview(target)

        send = NSButton(frame: NSRect(x: w - 46, y: (h - 32) / 2, width: 32, height: 32))
        send.isBordered = false
        send.wantsLayer = true
        send.layer?.cornerRadius = 9
        send.layer?.backgroundColor = text.cgColor          // Naim: white send button, not orange
        let arrow = NSImage(systemSymbolName: "arrow.up", accessibilityDescription: "Envoyer")?
            .withSymbolConfiguration(.init(pointSize: 14, weight: .bold))
        send.image = arrow
        send.contentTintColor = bg.withAlphaComponent(1)
        send.target = self
        send.action = #selector(submit)
        send.toolTip = "Envoyer (Entrée)"
        box.addSubview(send)
    }

    @objc func toggle() {
        if panel.isVisible { panel.orderOut(nil); return }
        let screen = NSScreen.screens.first(where: { $0.frame.contains(NSEvent.mouseLocation) }) ?? NSScreen.main
        if let f = screen?.visibleFrame {
            panel.setFrameOrigin(NSPoint(x: f.midX - panel.frame.width / 2, y: f.minY + f.height * 0.18))
        }
        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(field)
    }

    @objc func submit() {
        let t = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return }
        field.stringValue = ""
        panel.orderOut(nil)
        deliver?(t, target.indexOfSelectedItem == 0)
    }

    // Entrée sends, Échap closes
    func control(_ control: NSControl, textView: NSTextView, doCommandBy sel: Selector) -> Bool {
        if sel == #selector(NSResponder.insertNewline(_:)) { submit(); return true }
        if sel == #selector(NSResponder.cancelOperation(_:)) { panel.orderOut(nil); return true }
        return false
    }

    // clicking elsewhere closes the bar (what was typed stays for next time)
    func windowDidResignKey(_ notification: Notification) { panel.orderOut(nil) }
}
