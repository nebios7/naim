// Renders the Naim app icon (1024x1024 PNG): the name « Naim » in a serif face, light on a rounded dark square,
// with the thin line of the launch window under it (the same look as the app's launch screen, no robot).
import AppKit

let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()

// the macOS icon grid: a rounded square inset from the canvas, with a soft shadow
let inset: CGFloat = 100
let rect = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
let shape = NSBezierPath(roundedRect: rect, xRadius: 185, yRadius: 185)
NSGraphicsContext.saveGraphicsState()
let shadow = NSShadow()
shadow.shadowColor = NSColor(calibratedWhite: 0, alpha: 0.35)
shadow.shadowBlurRadius = 24
shadow.shadowOffset = NSSize(width: 0, height: -10)
shadow.set()
NSColor(calibratedRed: 0.086, green: 0.086, blue: 0.082, alpha: 1).setFill()   // #161615, like the launch window
shape.fill()
NSGraphicsContext.restoreGraphicsState()
// a faint light from the top, so the square is not flat
NSGradient(starting: NSColor(calibratedWhite: 1, alpha: 0.07), ending: NSColor(calibratedWhite: 1, alpha: 0))!
    .draw(in: shape, angle: -90)
NSColor(calibratedWhite: 1, alpha: 0.08).setStroke()
shape.lineWidth = 3
shape.stroke()

// « Naim » in a serif face (New York, else Georgia / Times)
let text = NSColor(calibratedRed: 0.910, green: 0.902, blue: 0.882, alpha: 1)    // #e8e6e1
func serif(_ size: CGFloat) -> NSFont {
    if let ny = NSFont.systemFont(ofSize: size, weight: .medium).fontDescriptor.withDesign(.serif),
       let f = NSFont(descriptor: ny, size: size) { return f }
    return NSFont(name: "Georgia", size: size) ?? NSFont(name: "Times New Roman", size: size)!
}
let font = serif(250)
let para = NSMutableParagraphStyle()
para.alignment = .center
let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: text, .kern: -6, .paragraphStyle: para]
let word = NSAttributedString(string: "Naim", attributes: attrs)
let wsize = word.size()
let wordY = (size - wsize.height) / 2 + 30
word.draw(in: NSRect(x: 0, y: wordY, width: size, height: wsize.height))

// the thin line of the launch window, under the name
let lineW: CGFloat = 250, lineH: CGFloat = 8, lineY = wordY - 38
NSColor(calibratedWhite: 1, alpha: 0.14).setFill()
NSBezierPath(roundedRect: NSRect(x: (size - lineW) / 2, y: lineY, width: lineW, height: lineH), xRadius: 4, yRadius: 4).fill()
text.withAlphaComponent(0.75).setFill()
NSBezierPath(roundedRect: NSRect(x: (size - lineW) / 2 + 40, y: lineY, width: 100, height: lineH), xRadius: 4, yRadius: 4).fill()

image.unlockFocus()

let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
let png = rep.representation(using: .png, properties: [:])!
try! png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
