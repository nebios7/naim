// Dictation for Naim's composer: macOS speech recognition (on this Mac when available), French by default.
// The page asks with window.webkit.messageHandlers.naimDictation.postMessage({action: "start" | "stop", lang})
// and receives the text with window.naimDictation(text, isFinal, error).
import AVFoundation
import Speech
import WebKit

final class NaimDictation: NSObject, WKScriptMessageHandler {
    weak var web: WKWebView?
    private let audio = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var recognizer: SFSpeechRecognizer?
    private var session = 0

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let action = body["action"] as? String else { return }
        if action == "start" {
            start(lang: body["lang"] as? String ?? "fr-FR")
        } else {
            stop()
        }
    }

    private func send(_ text: String, final: Bool, error: String? = nil) {
        let items: [Any] = [text, final, error.map { $0 as Any } ?? NSNull()]
        let payload = (try? JSONSerialization.data(withJSONObject: items)) ?? Data()
        let args = String(data: payload, encoding: .utf8) ?? "[\"\",true,null]"
        DispatchQueue.main.async {
            self.web?.evaluateJavaScript("window.naimDictation && window.naimDictation(...\(args))", completionHandler: nil)
        }
    }

    private func start(lang: String) {
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else {
                self.send("", final: true, error: "La reconnaissance vocale n'est pas autorisée : Réglages Système › Confidentialité › Reconnaissance vocale › Naim.")
                return
            }
            AVCaptureDevice.requestAccess(for: .audio) { ok in
                guard ok else {
                    self.send("", final: true, error: "Le micro n'est pas autorisé : Réglages Système › Confidentialité › Micro › Naim.")
                    return
                }
                DispatchQueue.main.async { self.begin(lang: lang) }
            }
        }
    }

    private func begin(lang: String) {
        stop()
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: lang))
        guard let recognizer = recognizer, recognizer.isAvailable else {
            send("", final: true, error: "La dictée n'est pas disponible pour cette langue.")
            return
        }
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition { req.requiresOnDeviceRecognition = true }  // stays on this Mac
        request = req
        let input = audio.inputNode
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
            req.append(buffer)
        }
        audio.prepare()
        do { try audio.start() } catch {
            send("", final: true, error: "Le micro ne démarre pas : \(error.localizedDescription)")
            return
        }
        session += 1
        let mine = session
        task = recognizer.recognitionTask(with: req) { result, error in
            guard mine == self.session else { return }  // a former listening: ignored
            if let result = result {
                self.send(result.bestTranscription.formattedString, final: result.isFinal)
                if result.isFinal { self.stop() }
            } else if error != nil {
                self.send("", final: true)
                self.stop()
            }
        }
    }

    private func stop() {
        if audio.isRunning {
            audio.stop()
            audio.inputNode.removeTap(onBus: 0)
        }
        request?.endAudio()
        request = nil
        session += 1    // from now on, the results of this listening are ignored
        task?.cancel()  // its late results (Naim's own voice, heard through the speakers) must not arrive afterwards
        task = nil
    }
}
