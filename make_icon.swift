// Renders the Naim app icon (1024x1024 PNG): the grey pixel robot on a rounded dark-grey square.
import AppKit

let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()

let inset: CGFloat = 100
let rect = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
NSColor(calibratedRed: 0.149, green: 0.149, blue: 0.141, alpha: 1).setFill()   // #262624
NSBezierPath(roundedRect: rect, xRadius: 185, yRadius: 185).fill()

// same 16x16 pixel robot as the web UI (x, y, w, h, color); y grows downward in the grid
let body = NSColor(calibratedRed: 0.788, green: 0.780, blue: 0.749, alpha: 1)   // #c9c7bf
let dark = NSColor(calibratedRed: 0.122, green: 0.118, blue: 0.114, alpha: 1)   // #1f1e1d
let eye = NSColor(calibratedRed: 0.941, green: 0.933, blue: 0.902, alpha: 1)    // #f0eee6
let pixels: [(CGFloat, CGFloat, CGFloat, CGFloat, NSColor)] = [
    (7, 0, 2, 2, eye), (7.5, 2, 1, 1, body), (3, 3, 10, 6, body), (2, 5, 1, 2, body), (13, 5, 1, 2, body),
    (4, 4, 8, 4, dark), (5, 5, 2, 2, eye), (9, 5, 2, 2, eye), (5, 9, 6, 4, body), (7, 10, 2, 1, dark),
    (3, 10, 2, 1, body), (11, 10, 2, 1, body), (5, 13, 2, 2, body), (9, 13, 2, 2, body),
]
let cell: CGFloat = 38
let origin = NSPoint(x: (size - 16 * cell) / 2, y: (size - 15 * cell) / 2)
for (x, y, w, h, color) in pixels {
    color.setFill()
    NSRect(x: origin.x + x * cell, y: size - origin.y - (y + h) * cell, width: w * cell, height: h * cell).fill()
}
image.unlockFocus()

let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
let png = rep.representation(using: .png, properties: [:])!
try! png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
