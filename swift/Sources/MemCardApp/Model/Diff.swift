import Foundation
import MemCardKit

/// Сравнение двух сейвов, свёрнутое по объектам.
///
/// По строкам сравнивать бесполезно: один добавленный предмет сдвигает
/// весь инвентарь и даёт сотни ложных различий. Поэтому сводим по имени
/// объекта, а одноимённых нумеруем - иначе четыре Мустадио слипаются
/// в одного, и различия последнего затирают предыдущих.
struct Diff {
    struct Row: Identifiable {
        let id = UUID()
        let label: String
        let left: String
        let right: String
    }

    struct Group: Identifiable {
        let id = UUID()
        let name: String
        let kind: String
        var rows: [Row]
    }

    var groups: [Group]
    var same: Int

    var count: Int { groups.reduce(0) { $0 + $1.rows.count } }

    static func between(_ left: LibraryItem, _ right: LibraryItem,
                        engine: Engine) -> Diff {
        var groups: [Group] = []
        var same = 0

        let leftDigest = Digest.of(left, engine: engine)
        let rightDigest = Digest.of(right, engine: engine)

        // Общее по сейву - всегда, даже когда разборщика нет.
        var common = Group(name: L.t("Общее", "General"), kind: L.t("сейв", "save"), rows: [])
        for (label, a, b) in [
            (L.t("Игра", "Game"), left.title, right.title),
            (L.t("Регион", "Region"), left.info.region, right.info.region),
            (L.t("Блоков", "Blocks"), String(left.blocks), String(right.blocks)),
            (L.t("Подпись", "Signature"), left.signature, right.signature),
        ] {
            if a == b { same += 1 } else {
                common.rows.append(Row(label: label, left: a, right: b))
            }
        }

        if let leftDigest, let rightDigest, leftDigest.game == rightDigest.game {
            var fields = Group(name: leftDigest.game, kind: L.t("поля", "fields"), rows: [])
            let rightByLabel = Dictionary(
                rightDigest.fields.map { ($0.label, $0.value) },
                uniquingKeysWith: { first, _ in first })
            for field in leftDigest.fields {
                guard let other = rightByLabel[field.label] else { continue }
                if field.value == other { same += 1 } else {
                    fields.rows.append(Row(label: field.label,
                                           left: field.value, right: other))
                }
            }
            if !fields.rows.isEmpty { groups.append(fields) }

            groups.append(contentsOf: members(leftDigest, rightDigest, same: &same))
        } else if leftDigest?.game != rightDigest?.game {
            common.rows.append(Row(label: L.t("Разбор", "Parsed"),
                                   left: leftDigest?.game ?? L.t("нет", "no"),
                                   right: rightDigest?.game ?? L.t("нет", "no")))
        }

        if !common.rows.isEmpty { groups.insert(common, at: 0) }
        return Diff(groups: groups, same: same)
    }

    /// Бойцы и прочие списки. Ключ - имя с номером у одноимённых.
    static func members(_ left: Digest, _ right: Digest,
                        same: inout Int) -> [Group] {
        let leftKeyed = numbered(left.members)
        let rightKeyed = numbered(right.members)
        var groups: [Group] = []

        for (key, member) in leftKeyed.sorted(by: { $0.key < $1.key }) {
            guard let other = rightKeyed[key] else {
                groups.append(Group(name: key, kind: left.membersTitle.lowercased(),
                                    rows: [Row(label: L.t("Есть", "Present"), left: L.t("да", "yes"), right: L.t("нет", "no"))]))
                continue
            }
            var rows: [Row] = []
            for (label, a, b) in [(L.t("Уровень", "Level"), member.level, other.level),
                                  (L.t("Класс", "Class"), member.role, other.role)] {
                if a == b { same += 1 } else {
                    rows.append(Row(label: label, left: a, right: b))
                }
            }
            if !rows.isEmpty {
                groups.append(Group(name: key, kind: left.membersTitle.lowercased(),
                                    rows: rows))
            }
        }
        for (key, _) in rightKeyed.sorted(by: { $0.key < $1.key })
        where leftKeyed[key] == nil {
            groups.append(Group(name: key, kind: right.membersTitle.lowercased(),
                                rows: [Row(label: L.t("Есть", "Present"), left: L.t("нет", "no"), right: L.t("да", "yes"))]))
        }
        return groups
    }

    /// Имена бывают неуникальны - нумеруем повторы.
    static func numbered(_ members: [Digest.Member]) -> [String: Digest.Member] {
        var seen: [String: Int] = [:]
        var out: [String: Digest.Member] = [:]
        for member in members {
            let base = member.name.isEmpty ? member.role : member.name
            seen[base, default: 0] += 1
            let count = seen[base] ?? 1
            out[count == 1 ? base : "\(base) #\(count)"] = member
        }
        return out
    }
}
