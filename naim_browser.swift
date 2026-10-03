// naim-browser: a real browser (the Mac's WebKit) that Naim drives to test web apps like a person would.
// One process per task: it reads one JSON command per line on stdin and answers one JSON line on stdout.
//   {"cmd":"open","url":"http://127.0.0.1:5050"}      load a page (waits for it), answers the page summary
//   {"cmd":"page"}                                     title, URL, visible text and numbered interactive elements
//   {"cmd":"click","target":"3"} / {"target":"Ajouter"}  click element [3] or the element showing that text
//   {"cmd":"type","target":"2","text":"…","submit":true} fill a field (then press Enter / submit its form)
//   {"cmd":"select","target":"4","value":"Paris"}     choose an option of a <select>
//   {"cmd":"key","key":"Enter"}  {"cmd":"scroll","dy":600}  {"cmd":"back"}
//   {"cmd":"eval","js":"document.title"}              run JavaScript, answers its result
//   {"cmd":"console"}                                  JavaScript errors, failed requests and console messages
//   {"cmd":"screenshot","path":"/tmp/x.png"}           image of the visible part of the page
import AppKit
import WebKit

func emit(_ obj: [String: Any]) {
    let data = (try? JSONSerialization.data(withJSONObject: obj, options: [])) ?? Data("{}".utf8)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
}

// Collected in the page from the very start: errors, rejected promises, failed resources, console output.
let captureJS = """
(() => { if (window.__naim) return; const log = []; window.__naim = { log };
  const push = (level, text) => { log.push({ level, text: String(text).slice(0, 500) }); if (log.length > 200) log.shift(); };
  for (const l of ['error', 'warn', 'log', 'info']) { const o = console[l]; console[l] = function (...a) {
    push(l, a.map(x => { try { return typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { return String(x); } }).join(' ')); return o.apply(this, a); }; }
  window.addEventListener('error', e => { if (e.target && e.target !== window && (e.target.src || e.target.href))
    push('error', 'ressource introuvable : ' + (e.target.src || e.target.href)); else push('error', (e.message || 'erreur') + (e.filename ? ' (' + e.filename.split('/').pop() + ':' + e.lineno + ')' : '')); }, true);
  window.addEventListener('unhandledrejection', e => push('error', 'promesse rejetée : ' + (e.reason && e.reason.message || e.reason)));
  const of = window.fetch; if (of) window.fetch = function (...a) { return of.apply(this, a).then(r => { if (!r.ok) push('error', 'fetch ' + r.status + ' ' + r.url); return r; },
    err => { push('error', 'fetch impossible : ' + (a[0] && a[0].url || a[0]) + ' — ' + err); throw err; }); };
})();
"""

// Numbered list of what can be clicked or filled, plus the visible text.
let pageJS = """
(() => { const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = el => { const t = (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || el.title || el.alt || el.name || '').trim().replace(/\\s+/g, ' ');
    if (!t && el.id) { const l = document.querySelector('label[for="' + el.id + '"]'); if (l) return l.innerText.trim(); } return t.slice(0, 80); };
  document.querySelectorAll('[data-naim-id]').forEach(e => e.removeAttribute('data-naim-id'));
  const els = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), textarea, select, [role=button], [role=link], [role=tab], [role=checkbox], [onclick], summary')].filter(vis).slice(0, 120);
  const items = els.map((el, i) => { el.setAttribute('data-naim-id', i + 1); const tag = el.tagName.toLowerCase();
    const kind = tag === 'a' ? 'lien' : tag === 'button' || el.getAttribute('role') === 'button' ? 'bouton' : tag === 'select' ? 'liste' : tag === 'textarea' ? 'zone de texte' : tag === 'input' ? 'champ ' + (el.type || 'text') : tag;
    const extra = (tag === 'input' || tag === 'textarea') && el.value ? ' = "' + String(el.value).slice(0, 40) + '"' : tag === 'input' && (el.type === 'checkbox' || el.type === 'radio') ? (el.checked ? ' ☑' : ' ☐') : el.disabled ? ' (désactivé)' : '';
    return '[' + (i + 1) + '] ' + kind + ' « ' + label(el) + ' »' + extra; });
  const text = (document.body ? document.body.innerText : '').replace(/\\n{3,}/g, '\\n\\n').trim();
  return JSON.stringify({ title: document.title, url: location.href, text: text.slice(0, 5000), textLength: text.length, elements: items }); })()
"""

func findJS(_ target: String) -> String {
    let t = target.trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
    let lit = String(data: try! JSONSerialization.data(withJSONObject: [t], options: []), encoding: .utf8)!
    return """
    const __t = \(lit)[0]; let el = /^\\d+$/.test(__t) ? document.querySelector('[data-naim-id="' + __t + '"]') : null;
    if (!el && !/^\\d+$/.test(__t)) { try { el = document.querySelector(__t); } catch (e) {} }
    if (!el) { const want = __t.toLowerCase(); const all = [...document.querySelectorAll('a, button, input, textarea, select, label, [role], summary, [onclick], li, td, span, div')];
      const txt = e => (e.getAttribute('aria-label') || e.innerText || e.value || e.placeholder || '').trim().toLowerCase();
      el = all.find(e => txt(e) === want) || all.filter(e => txt(e).includes(want)).sort((a, b) => txt(a).length - txt(b).length)[0]; }
    """
}

class Browser: NSObject, WKNavigationDelegate {
    let web: WKWebView
    let window: NSWindow
    var loaded: (() -> Void)?
    var status = 0
    var navError = ""

    override init() {
        let config = WKWebViewConfiguration()
        config.userContentController.addUserScript(WKUserScript(source: captureJS, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        config.websiteDataStore = .nonPersistent()  // clean session each task: no cookies from elsewhere
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: 1280, height: 800), configuration: config)
        window = NSWindow(contentRect: web.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        super.init()
        window.contentView = web
        web.navigationDelegate = self
        web.customUserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15 Naim"
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if response.isForMainFrame, let h = response.response as? HTTPURLResponse { status = h.statusCode }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { finishLoad() }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { navError = error.localizedDescription; finishLoad() }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { navError = error.localizedDescription; finishLoad() }

    func finishLoad() {
        guard let cb = loaded else { return }
        loaded = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { cb() }  // let scripts render the page
    }

    func page(_ extra: [String: Any] = [:]) {
        web.evaluateJavaScript(pageJS) { r, err in
            var out: [String: Any] = extra
            if let s = r as? String, let d = s.data(using: .utf8), let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                out.merge(obj) { a, _ in a }
            } else if let err = err { out["error"] = "page illisible : \(err.localizedDescription)" }
            if self.status > 0 { out["status"] = self.status }
            self.web.evaluateJavaScript("(window.__naim ? window.__naim.log.filter(x => x.level === 'error').length : 0)") { n, _ in
                out["js_errors"] = (n as? Int) ?? 0
                emit(out)
            }
        }
    }

    func settle(_ then: @escaping () -> Void) {  // after an action: wait for a possible navigation / rendering
        var done = false
        loaded = { if !done { done = true; then() } }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) {
            if !done && !self.web.isLoading { done = true; self.loaded = nil; then() }
            else if !done { DispatchQueue.main.asyncAfter(deadline: .now() + 8) { if !done { done = true; self.loaded = nil; then() } } }
        }
    }

    func run(_ c: [String: Any]) {
        let cmd = c["cmd"] as? String ?? ""
        switch cmd {
        case "open":
            guard let s = c["url"] as? String, let url = URL(string: s.contains("://") ? s : "http://" + s) else { emit(["error": "adresse invalide"]); return }
            status = 0; navError = ""
            loaded = { if !self.navError.isEmpty { emit(["error": "chargement impossible : \(self.navError)", "url": s]) } else { self.page() } }
            if url.isFileURL { web.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent()) } else { web.load(URLRequest(url: url)) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) { if self.loaded != nil { self.loaded = nil; emit(["error": "la page ne répond pas (30 s)", "url": s]) } }
        case "page":
            page()
        case "click":
            let js = "(() => {" + findJS(c["target"] as? String ?? "") + """
            if (!el) return 'introuvable'; el.scrollIntoView({block: 'center'}); el.focus && el.focus();
            setTimeout(() => el.click(), 0);  // an error inside the page's handler is the page's, not a failed click
            return 'ok'; })()
            """
            web.evaluateJavaScript(js) { r, err in
                if (r as? String) != "ok" { emit(["error": err.map { "clic impossible : \($0.localizedDescription)" } ?? "élément introuvable : \(c["target"] ?? "") — appelle page pour voir la liste"]); return }
                self.status = 0
                self.settle { self.page(["action": "clic fait"]) }
            }
        case "type", "select":
            let value = (c["text"] ?? c["value"]) as? String ?? ""
            let lit = String(data: try! JSONSerialization.data(withJSONObject: [value], options: []), encoding: .utf8)!
            let submit = (c["submit"] as? Bool) ?? false
            let js = "(() => {" + findJS(c["target"] as? String ?? "") + """
            const __v = \(lit)[0];
            if (!el) return 'introuvable'; el.scrollIntoView({block: 'center'}); el.focus && el.focus();
            if (el.tagName === 'SELECT') { const o = [...el.options].find(o => o.value === __v || o.text.trim().toLowerCase() === __v.toLowerCase());
              if (!o) return 'option introuvable'; el.value = o.value; el.dispatchEvent(new Event('change', {bubbles: true})); return 'ok'; }
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value'); if (setter && setter.set) setter.set.call(el, __v); else el.value = __v;
            el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true}));
            if (\(submit ? "true" : "false")) { el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
              if (el.form) { el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit(); } }
            return 'ok'; })()
            """
            web.evaluateJavaScript(js) { r, err in
                guard (r as? String) == "ok" else { emit(["error": (r as? String) == "option introuvable" ? "option introuvable : \(value)" : "champ introuvable : \(c["target"] ?? "")"]); return }
                self.status = 0
                self.settle { self.page(["action": submit ? "saisi et envoyé" : "saisi"]) }
            }
        case "key":
            let key = c["key"] as? String ?? "Enter"
            let lit = String(data: try! JSONSerialization.data(withJSONObject: [key], options: []), encoding: .utf8)!
            let js = """
            (() => { const k = \(lit)[0]; const el = document.activeElement || document.body;
              for (const t of ['keydown', 'keypress', 'keyup']) el.dispatchEvent(new KeyboardEvent(t, {key: k, code: k, keyCode: k === 'Enter' ? 13 : k === 'Escape' ? 27 : 0, bubbles: true}));
              if (k === 'Enter' && el.form) { el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit(); } return 'ok'; })()
            """
            web.evaluateJavaScript(js) { _, _ in self.settle { self.page(["action": "touche \(key)"]) } }
        case "scroll":
            let dy = (c["dy"] as? Double) ?? 600
            web.evaluateJavaScript("window.scrollBy(0, \(dy)); 'ok'") { _, _ in self.page(["action": "défilé"]) }
        case "back":
            loaded = { self.page(["action": "retour"]) }
            if web.canGoBack { web.goBack() } else { loaded = nil; emit(["error": "pas de page précédente"]) }
        case "eval":
            web.evaluateJavaScript(c["js"] as? String ?? "") { r, err in
                if let err = err { emit(["error": "JavaScript : \(err.localizedDescription)"]); return }
                var text = "undefined"
                if let r = r { text = (r as? String) ?? ((try? JSONSerialization.data(withJSONObject: r, options: [.fragmentsAllowed])).flatMap { String(data: $0, encoding: .utf8) } ?? "\(r)") }
                emit(["result": String(text.prefix(4000))])
            }
        case "console":
            web.evaluateJavaScript("JSON.stringify(window.__naim ? window.__naim.log : [])") { r, _ in
                let s = r as? String ?? "[]"
                let arr = (try? JSONSerialization.jsonObject(with: Data(s.utf8))) as? [[String: Any]] ?? []
                emit(["log": arr, "errors": arr.filter { ($0["level"] as? String) == "error" }.count])
            }
        case "screenshot":
            let path = c["path"] as? String ?? NSTemporaryDirectory() + "naim-page.png"
            let conf = WKSnapshotConfiguration()
            conf.afterScreenUpdates = true
            web.takeSnapshot(with: conf) { img, err in
                guard let img = img, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
                      let data = rep.representation(using: .png, properties: [:]), (try? data.write(to: URL(fileURLWithPath: path))) != nil
                else { emit(["error": "capture impossible : \(err?.localizedDescription ?? "?")"]); return }
                emit(["path": path, "width": rep.pixelsWide, "height": rep.pixelsHigh])
            }
        case "quit":
            emit(["ok": true]); exit(0)
        default:
            emit(["error": "commande inconnue : \(cmd)"])
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let browser = Browser()
DispatchQueue.global().async {
    while let line = readLine() {
        guard let d = line.data(using: .utf8), let c = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] else {
            DispatchQueue.main.async { emit(["error": "commande illisible"]) }; continue
        }
        DispatchQueue.main.async { browser.run(c) }  // Naim waits for each answer before sending the next command
    }
    exit(0)
}
app.run()
