// Modèle d'application Mac en SwiftUI (design soigné) — compile tel quel.
// Copie-le, renomme MonApp / « Mon application », puis adapte : Element, charger(), DetailView.
// Garde la structure : barre latérale + détail, barre d'outils, carte d'en-tête, sections, bandeau d'état.
import SwiftUI
import AppKit
import UniformTypeIdentifiers

@main
struct MonApp: App {
    var body: some Scene {
        WindowGroup("Mon application") {
            ContentView().frame(minWidth: 820, minHeight: 520)
        }
        .windowToolbarStyle(.unified)
    }
}

// Un élément de la liste (une imprimante, un fichier, un appareil…) : toujours de VRAIES données
struct Element: Identifiable, Hashable {
    let id: String
    var nom: String
    var detail: String
    var symbole: String        // icône SF Symbols : "printer", "doc", "wifi", "externaldrive"…
    var actif: Bool
}

// Le message affiché en bas de la fenêtre après une action
struct Etat: Equatable {
    var texte: String
    var ok: Bool
}

struct ContentView: View {
    @State private var elements: [Element] = []
    @State private var selection: Element.ID? = nil
    @State private var recherche = ""
    @State private var chargement = false
    @State private var etat: Etat? = nil

    var filtres: [Element] {
        recherche.isEmpty ? elements : elements.filter { $0.nom.localizedCaseInsensitiveContains(recherche) }
    }

    var body: some View {
        NavigationSplitView {
            List(filtres, selection: $selection) { e in
                HStack(spacing: 10) {
                    Image(systemName: e.symbole)
                        .font(.title3)
                        .foregroundStyle(.tint)
                        .frame(width: 26)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(e.nom).font(.body.weight(.medium)).lineLimit(1)
                        Text(e.detail).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }
                    Spacer()
                    Circle().fill(e.actif ? Color.green : Color.secondary.opacity(0.4)).frame(width: 8, height: 8)
                }
                .padding(.vertical, 4)
            }
            .searchable(text: $recherche, placement: .sidebar, prompt: "Rechercher")
            .overlay {
                if !chargement && filtres.isEmpty {
                    ContentUnavailableView("Rien à afficher", systemImage: "tray",
                                           description: Text("Clique sur Actualiser pour chercher à nouveau."))
                }
            }
            .navigationSplitViewColumnWidth(min: 240, ideal: 280)
        } detail: {
            if let e = elements.first(where: { $0.id == selection }) {
                DetailView(element: e, etat: $etat)
            } else {
                ContentUnavailableView("Choisis un élément", systemImage: "sidebar.left",
                                       description: Text("Sélectionne un élément dans la liste à gauche."))
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                if chargement { ProgressView().controlSize(.small) }
                else { Button { Task { await charger() } } label: { Label("Actualiser", systemImage: "arrow.clockwise") } }
            }
        }
        .safeAreaInset(edge: .bottom) {
            if let etat {
                HStack(spacing: 8) {
                    Image(systemName: etat.ok ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(etat.ok ? .green : .orange)
                    Text(etat.texte).font(.callout).textSelection(.enabled).lineLimit(2)
                    Spacer()
                    Button { self.etat = nil } label: { Image(systemName: "xmark") }.buttonStyle(.borderless)
                }
                .padding(10)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
                .padding(12)
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.easeOut(duration: 0.2), value: etat)
        .task { await charger() }
    }

    // Exemple : les imprimantes du Mac. Remplace par ta vraie source (une commande, un dossier…).
    func charger() async {
        chargement = true
        let sortie = await lancerAsync("/usr/bin/lpstat", ["-a"])
        elements = sortie.split(separator: "\n").compactMap { ligne in
            guard let nom = ligne.split(separator: " ").first.map(String.init) else { return nil }
            let pret = ligne.contains("accept")
            return Element(id: nom, nom: nom.replacingOccurrences(of: "_", with: " "),
                           detail: pret ? "Prête" : "Indisponible", symbole: "printer", actif: pret)
        }
        if selection == nil { selection = elements.first?.id }
        chargement = false
    }
}

// Le détail de l'élément choisi : carte d'en-tête, puis des sections avec les actions
struct DetailView: View {
    let element: Element
    @Binding var etat: Etat?
    @State private var fichier: URL? = nil
    @State private var occupe = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // carte d'en-tête
                HStack(spacing: 16) {
                    Image(systemName: element.symbole)
                        .font(.system(size: 30, weight: .medium))
                        .foregroundStyle(.white)
                        .frame(width: 60, height: 60)
                        .background(LinearGradient(colors: [.accentColor, .accentColor.opacity(0.7)],
                                                   startPoint: .topLeading, endPoint: .bottomTrailing),
                                    in: RoundedRectangle(cornerRadius: 14))
                    VStack(alignment: .leading, spacing: 4) {
                        Text(element.nom).font(.title2.weight(.semibold))
                        Text(element.detail).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(element.actif ? "En ligne" : "Hors ligne")
                        .font(.caption.weight(.semibold))
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background((element.actif ? Color.green : Color.secondary).opacity(0.15), in: Capsule())
                        .foregroundStyle(element.actif ? Color.green : Color.secondary)
                }
                .padding(18)
                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 16))

                // une section = un titre + son contenu dans une carte
                Carte(titre: "Imprimer un document", symbole: "doc.richtext") {
                    HStack {
                        Label(fichier?.lastPathComponent ?? "Aucun fichier choisi", systemImage: "doc")
                            .foregroundStyle(fichier == nil ? .secondary : .primary)
                            .lineLimit(1)
                        Spacer()
                        Button("Choisir…") { fichier = choisirFichier() }
                    }
                    HStack {
                        Spacer()
                        Button {
                            guard let f = fichier else { return }
                            occupe = true
                            Task {
                                let sortie = await lancerAsync("/usr/bin/lp", ["-d", element.id, f.path])
                                let ok = !sortie.lowercased().contains("erreur") && !sortie.lowercased().contains("error")
                                etat = Etat(texte: ok ? "Envoyé à \(element.nom). \(sortie)" : sortie, ok: ok)
                                occupe = false
                            }
                        } label: {
                            if occupe { ProgressView().controlSize(.small) } else { Label("Imprimer", systemImage: "printer.fill") }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .disabled(fichier == nil || occupe)
                    }
                }

                Carte(titre: "Informations", symbole: "info.circle") {
                    LigneInfo(nom: "Nom", valeur: element.id)
                    Divider()
                    LigneInfo(nom: "État", valeur: element.detail)
                }
            }
            .padding(24)
            .frame(maxWidth: 720, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .navigationTitle(element.nom)
    }
}

// Une section : un titre avec icône, et son contenu dans une carte arrondie
struct Carte<Contenu: View>: View {
    let titre: String
    let symbole: String
    @ViewBuilder var contenu: Contenu
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(titre, systemImage: symbole).font(.headline)
            VStack(alignment: .leading, spacing: 12) { contenu }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
        }
    }
}

struct LigneInfo: View {
    let nom: String
    let valeur: String
    var body: some View {
        HStack {
            Text(nom).foregroundStyle(.secondary)
            Spacer()
            Text(valeur).textSelection(.enabled)
        }
    }
}

// Choisir un fichier (fenêtre « Ouvrir » du Mac)
func choisirFichier() -> URL? {
    let panneau = NSOpenPanel()
    panneau.allowsMultipleSelection = false
    panneau.allowedContentTypes = [.pdf, .plainText, .image, .rtf]
    return panneau.runModal() == .OK ? panneau.url : nil
}

// Lancer une commande du Mac et récupérer ce qu'elle affiche (chemin complet de la commande)
func lancer(_ commande: String, _ arguments: [String]) -> String {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: commande)
    p.arguments = arguments
    let sortie = Pipe()
    p.standardOutput = sortie
    p.standardError = sortie
    do { try p.run() } catch { return "Erreur : \(error.localizedDescription)" }
    let data = sortie.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    return String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
}

// La même chose sans bloquer la fenêtre (à utiliser dans les boutons et au chargement)
func lancerAsync(_ commande: String, _ arguments: [String]) async -> String {
    await Task.detached { lancer(commande, arguments) }.value
}
