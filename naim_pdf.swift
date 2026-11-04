// naim-pdf: renders an HTML file with the Mac's own WebKit (no install needed).
// Usage: naim-pdf <in.html> <out.pdf|out.png|out.svg> [A4|letter|fit] [portrait|landscape]
//   .pdf  paginated document (A4 / letter); with "fit": one page exactly the size of the content (diagrams)
//   .png  image of the content (2x, sharp); .svg  the first <svg> of the page (Mermaid, charts)
// CSS works as in Safari (flex, grid, colors); `page-break-before: always` starts a new page.
// naim-pdf <in.pdf> <out.png> [page] [max width]  renders one page of a PDF to an image (visual checks).
// A page that sets `window.__naimWait = true` is captured only once it sets `window.__naimReady = true`
// (or `window.__naimError = "..."`), e.g. after Mermaid has drawn the diagram.
import AppKit
import WebKit
import PDFKit

let args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 2 else {
    FileHandle.standardError.write("usage: naim-pdf <in.html> <out.pdf|png|svg> [A4|letter|fit] [portrait|landscape]\n".data(using: .utf8)!)
    exit(2)
}
let input = URL(fileURLWithPath: args[0]).standardizedFileURL
let output = URL(fileURLWithPath: args[1]).standardizedFileURL
let kind = output.pathExtension.lowercased()
let paperArg = args.count > 2 ? args[2].lowercased() : "a4"
let letter = paperArg == "letter"
let fit = paperArg == "fit"
let landscape = args.count > 3 && args[3].lowercased() == "landscape"

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(1)
}

let errorsJS = """
window.__naimErrors = [];
addEventListener('error', e => { const t = e.target; __naimErrors.push(t && t !== window && (t.src || t.href)
  ? 'fichier introuvable : ' + (t.src || t.href) : (e.message || 'erreur') + (e.lineno ? ' (ligne ' + e.lineno + ')' : '')); }, true);
addEventListener('unhandledrejection', e => __naimErrors.push(String(e.reason && e.reason.message || e.reason)));
const __naimCE = console.error;
console.error = function (...a) { __naimErrors.push(a.map(String).join(' ')); return __naimCE.apply(this, a); };
"""

func jsonList(_ items: [String]) -> String {
    let data = (try? JSONSerialization.data(withJSONObject: items)) ?? Data("[]".utf8)
    return String(data: data, encoding: .utf8) ?? "[]"
}

func done(_ extra: String = "") -> Never {
    print("{\"file\": \"\(output.path)\"\(extra)}")
    exit(0)
}

class Renderer: NSObject, WKNavigationDelegate {
    let web: WKWebView
    let window: NSWindow
    var tries = 0

    init(size: NSSize) {
        let config = WKWebViewConfiguration()
        if #available(macOS 13.3, *) { config.preferences.shouldPrintBackgrounds = true }  // colored blocks, banners
        let css = "*{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important}"
        config.userContentController.addUserScript(WKUserScript(
            source: "var s=document.createElement('style');s.textContent='\(css)';document.head.appendChild(s);",
            injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        // what the page itself reports as broken (a script error, a missing file): returned with the image
        config.userContentController.addUserScript(WKUserScript(source: errorsJS, injectionTime: .atDocumentStart,
                                                                forMainFrameOnly: true))
        web = WKWebView(frame: NSRect(origin: .zero, size: size), configuration: config)
        window = NSWindow(contentRect: web.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        super.init()
        window.contentView = web
        web.navigationDelegate = self
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.waitReady() }  // web fonts / images
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        fail("chargement impossible : \(error.localizedDescription)")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        fail("chargement impossible : \(error.localizedDescription)")
    }

    func waitReady() {
        web.evaluateJavaScript("[window.__naimWait === true, window.__naimReady === true, String(window.__naimError || '')]") { r, _ in
            let a = r as? [Any] ?? [false, true, ""]
            let wait = a[0] as? Bool ?? false, ready = a[1] as? Bool ?? true, err = a[2] as? String ?? ""
            if !err.isEmpty { fail(err) }
            if wait && !ready {
                self.tries += 1
                if self.tries > 200 { fail("la page n'a pas fini de se dessiner (20 s)") }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { self.waitReady() }
                return
            }
            switch kind {
            case "png": self.png()
            case "svg": self.svg()
            default: fit ? self.fitPDF() : self.pagedPDF()
            }
        }
    }

    // size of the content: the #naim-capture element if any, else the whole document
    let boundsJS = """
    (() => { const el = document.querySelector('#naim-capture') || document.documentElement;
      const r = el.getBoundingClientRect();
      const whole = el === document.documentElement;
      const w = whole ? Math.max(el.scrollWidth, document.body.scrollWidth) : r.width;
      const h = whole ? Math.max(el.scrollHeight, document.body.scrollHeight) : r.height;
      return [whole ? 0 : r.left + window.scrollX, whole ? 0 : r.top + window.scrollY, Math.ceil(w), Math.ceil(h)]; })()
    """

    func withBounds(_ then: @escaping (NSRect) -> Void) {
        web.evaluateJavaScript(boundsJS) { r, _ in
            let a = (r as? [NSNumber])?.map { CGFloat($0.doubleValue) } ?? [0, 0, 800, 600]
            let rect = NSRect(x: a[0], y: a[1], width: max(a[2], 10), height: max(a[3], 10))
            // grow the view so everything is laid out, then measure again once
            let need = NSSize(width: max(self.web.frame.width, rect.maxX), height: max(self.web.frame.height, rect.maxY))
            if need.width > self.web.frame.width + 1 || need.height > self.web.frame.height + 1 {
                self.window.setContentSize(need); self.web.setFrameSize(need)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                    self.web.evaluateJavaScript(self.boundsJS) { r2, _ in
                        let b = (r2 as? [NSNumber])?.map { CGFloat($0.doubleValue) } ?? a
                        then(NSRect(x: b[0], y: b[1], width: max(b[2], 10), height: max(b[3], 10)))
                    }
                }
            } else {
                then(rect)
            }
        }
    }

    func png() {
        withBounds { rect in
            let conf = WKSnapshotConfiguration()
            conf.rect = rect
            conf.afterScreenUpdates = true
            // 2x image whatever the screen: snapshotWidth is in points, multiplied by the display's backing scale
            let backing = self.window.backingScaleFactor > 0 ? self.window.backingScaleFactor : 1
            conf.snapshotWidth = NSNumber(value: Double(rect.width * 2 / backing))
            self.web.takeSnapshot(with: conf) { img, err in
                guard let img = img, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
                      let data = rep.representation(using: .png, properties: [:]) else {
                    fail("capture impossible : \(err?.localizedDescription ?? "?")")
                }
                do { try data.write(to: output) } catch { fail("écriture impossible : \(error.localizedDescription)") }
                self.report(rep, rect) { extra in
                    done(", \"width\": \(rep.pixelsWide), \"height\": \(rep.pixelsHigh)" + extra)
                }
            }
        }
    }

    // the page's errors, and each canvas (3D, chart, game) that is one flat colour in the image: nothing drawn in it
    func report(_ rep: NSBitmapImageRep, _ rect: NSRect, _ then: @escaping (String) -> Void) {
        // per canvas, the points of a 12 × 12 grid where it is visible (not under a title or a legend)
        let js = """
        [(window.__naimErrors || []).slice(0, 12).map(String),
         [...document.querySelectorAll('canvas')].map(c => { const r = c.getBoundingClientRect(), pts = [];
           if (r.width < 40 || r.height < 40) return null;
           for (let i = 1; i < 12; i++) for (let j = 1; j < 12; j++) {
             const x = r.left + r.width * i / 12, y = r.top + r.height * j / 12;
             if (document.elementFromPoint(x, y) === c) pts.push([x + scrollX, y + scrollY]); }
           return pts; }).filter(p => p)]
        """
        web.evaluateJavaScript(js) { r, _ in
            let a = r as? [Any] ?? []
            let errors = a.first as? [String] ?? []
            let canvases = (a.count > 1 ? a[1] as? [[[NSNumber]]] : nil) ?? []
            let k = CGFloat(rep.pixelsWide) / max(rect.width, 1)
            var blank = 0
            for pts in canvases {
                var first: NSColor?, flat = true, seen = 0
                for pt in pts where pt.count == 2 {
                    let x = Int((CGFloat(pt[0].doubleValue) - rect.minX) * k), y = Int((CGFloat(pt[1].doubleValue) - rect.minY) * k)
                    guard x >= 0, y >= 0, x < rep.pixelsWide, y < rep.pixelsHigh,
                          let c = rep.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { continue }
                    seen += 1
                    if let f = first {
                        if abs(f.redComponent - c.redComponent) + abs(f.greenComponent - c.greenComponent)
                            + abs(f.blueComponent - c.blueComponent) > 0.06 { flat = false }
                    } else { first = c }
                }
                if flat && seen >= 20 { blank += 1 }
            }
            then(", \"errors\": \(jsonList(errors)), \"canvas\": \(canvases.count), \"blank\": \(blank)")
        }
    }

    func svg() {
        let js = """
        (() => { const s = document.querySelector('#naim-capture svg') || document.querySelector('svg');
          if (!s) return ''; if (!s.getAttribute('xmlns')) s.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
          return s.outerHTML; })()
        """
        web.evaluateJavaScript(js) { r, _ in
            guard let text = r as? String, !text.isEmpty else { fail("aucun <svg> dans la page") }
            do { try ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + text).write(to: output, atomically: true, encoding: .utf8) }
            catch { fail("écriture impossible : \(error.localizedDescription)") }
            done()
        }
    }

    func fitPDF() {
        withBounds { rect in
            let conf = WKPDFConfiguration()
            conf.rect = rect
            self.web.createPDF(configuration: conf) { result in
                switch result {
                case .success(let data):
                    do { try data.write(to: output) } catch { fail("écriture impossible : \(error.localizedDescription)") }
                    done(", \"pages\": 1")
                case .failure(let e): fail("création du PDF impossible : \(e.localizedDescription)")
                }
            }
        }
    }

    func pagedPDF() {
        let info = NSPrintInfo()
        var paper = letter ? NSSize(width: 612, height: 792) : NSSize(width: 595.28, height: 841.89)
        if landscape { paper = NSSize(width: paper.height, height: paper.width) }
        info.paperSize = paper
        info.orientation = landscape ? .landscape : .portrait
        info.topMargin = 0; info.bottomMargin = 0; info.leftMargin = 0; info.rightMargin = 0  // margins come from the CSS
        info.horizontalPagination = .fit
        info.verticalPagination = .automatic
        info.isHorizontallyCentered = false
        info.isVerticallyCentered = false
        info.jobDisposition = .save
        info.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = output
        try? FileManager.default.removeItem(at: output)
        let op = web.printOperation(with: info)
        op.showsPrintPanel = false
        op.showsProgressPanel = false
        op.view?.frame = web.bounds
        op.runModal(for: window, delegate: self, didRun: #selector(printed(_:success:context:)), contextInfo: nil)
    }

    @objc func printed(_ op: NSPrintOperation, success: Bool, context: UnsafeMutableRawPointer?) {
        guard success, FileManager.default.fileExists(atPath: output.path) else { fail("création du PDF impossible") }
        numberPages(output)
        done(", \"pages\": \(CGPDFDocument(output as CFURL)?.numberOfPages ?? 0)")
    }

    // « 2 / 17 » at the foot of every page but the first (a cover, or a one-page letter): a long document is found
    // again page by page. Drawn into the page itself (every viewer and printer shows it), the links put back after
    func numberPages(_ url: URL) {
        guard let src = CGPDFDocument(url as CFURL), src.numberOfPages > 1, let links = PDFDocument(url: url) else { return }
        let n = src.numberOfPages
        let data = NSMutableData()
        guard let consumer = CGDataConsumer(data: data as CFMutableData),
              let ctx = CGContext(consumer: consumer, mediaBox: nil, nil) else { return }
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 8),
            .foregroundColor: NSColor(calibratedRed: 0.55, green: 0.53, blue: 0.50, alpha: 1)]
        for i in 1...n {
            guard let page = src.page(at: i) else { continue }
            var box = page.getBoxRect(.mediaBox)
            ctx.beginPage(mediaBox: &box)
            ctx.drawPDFPage(page)
            if i > 1 {
                let text = NSAttributedString(string: "\(i) / \(n)", attributes: attrs)
                NSGraphicsContext.saveGraphicsState()
                NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
                text.draw(at: NSPoint(x: box.midX - text.size().width / 2, y: box.minY + 24))
                NSGraphicsContext.restoreGraphicsState()
            }
            ctx.endPage()
        }
        ctx.closePDF()
        guard let numbered = PDFDocument(data: data as Data) else { return }
        for i in 0..<min(n, links.pageCount, numbered.pageCount) {  // the contents' links, clickable again
            guard let from = links.page(at: i), let to = numbered.page(at: i) else { continue }
            for ann in from.annotations where ann.type == "Link" {
                if let copy = ann.copy() as? PDFAnnotation { to.addAnnotation(copy) }
            }
        }
        numbered.write(to: url)
    }
}

if input.pathExtension.lowercased() == "pdf" {
    guard let doc = CGPDFDocument(input as CFURL) else { fail("PDF illisible") }
    let n = max(Int(args.count > 2 ? args[2] : "1") ?? 1, 1)
    if n > doc.numberOfPages { fail("page \(n) introuvable (le PDF a \(doc.numberOfPages) pages)") }
    guard let page = doc.page(at: n) else { fail("page \(n) introuvable (le PDF a \(doc.numberOfPages) pages)") }
    let box = page.getBoxRect(.mediaBox)
    let maxW = CGFloat(Double(args.count > 3 ? args[3] : "1100") ?? 1100)
    let scale = maxW / box.width
    let w = Int(box.width * scale), h = Int(box.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
    else { fail("rendu impossible") }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -box.minX, y: -box.minY)
    ctx.drawPDFPage(page)
    guard let img = ctx.makeImage(), let data = NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])
    else { fail("rendu impossible") }
    do { try data.write(to: output) } catch { fail("écriture impossible : \(error.localizedDescription)") }
    done(", \"page\": \(n), \"pages\": \(doc.numberOfPages), \"width\": \(w), \"height\": \(h)")
}

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let width: CGFloat = (kind == "pdf" && !fit) ? (landscape ? (letter ? 792 : 842) : (letter ? 612 : 595)) : 1200
let renderer = Renderer(size: NSSize(width: width, height: 842))
renderer.web.loadFileURL(input, allowingReadAccessTo: URL(fileURLWithPath: "/"))
DispatchQueue.main.asyncAfter(deadline: .now() + 90) { fail("délai dépassé (90 s)") }
app.run()
