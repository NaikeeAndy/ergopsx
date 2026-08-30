import Foundation
import MemCardKit

/// Разбор сейва к тому виду, в каком его показывает панель справа.
///
/// Каждая игра устроена по-своему, но показать её нужно одинаково:
/// сводка сверху, состав отряда с их числами и экипировкой, и списки -
/// инвентарь, магия, реликвии, кто что собрал.
struct Digest {
    struct Field: Identifiable {
        let id = UUID()
        let label: String
        let value: String
    }

    /// Боец, персонаж, фамильяр - всё, что показывается строкой с числами.
    struct Member: Identifiable {
        let id = UUID()
        var name: String
        var role: String
        var level: String
        /// Числа бойца: HP, MP, статы. Пары «подпись, значение».
        var stats: [Field] = []
        /// Что надето.
        var gear: [String] = []
        /// Мелочи в одну строку: зодиак, пол, гость, транс.
        var extra: String = ""
    }

    /// Список: инвентарь, магия, реликвии, бестиарий.
    struct Section: Identifiable {
        let id = UUID()
        var title: String
        /// Пары «название, количество». Количество бывает пустым.
        var items: [Field]
        var note: String = ""
    }

    var game: String
    /// Наигранное время в секундах - по нему сортируется список.
    /// Не у всех игр оно есть, поэтому необязательное.
    var playtime: Int?
    var fields: [Field]
    var members: [Member]
    var membersTitle: String
    var sections: [Section]

    static func time(_ parts: [Int]) -> String {
        guard parts.count >= 3 else { return "—" }
        return String(format: "%d:%02d:%02d", parts[0], parts[1], parts[2])
    }

    static func number(_ value: some BinaryInteger) -> String {
        let text = String(describing: value)
        var out = ""
        for (index, character) in text.reversed().enumerated() {
            if index > 0, index % 3 == 0 { out.append("\u{202F}") }
            out.append(character)
        }
        return String(out.reversed())
    }

    /// Часы, минуты, секунды в одно число.
    static func total(_ parts: [Int]) -> Int? {
        guard parts.count >= 3 else { return nil }
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    }

    static func pairs(_ list: [[String]]) -> [Field] {
        list.compactMap { row in
            guard let name = row.first else { return nil }
            return Field(label: name, value: row.count > 1 ? row[1] : "")
        }
    }

    /// Разбор одного и того же сейва не меняется, а панель справа
    /// перестраивается на каждый обход вьюхи - поэтому помним результат.
    private static let cache = Mutex<[String: Digest?]>([:])

    /// Разбор помнит подписи полей, а они зависят от языка.
    static func forget() { cache.withLock { $0 = [:] } }

    static func of(_ item: LibraryItem, engine: Engine) -> Digest? {
        if let found = cache.withLock({ $0[item.fingerprint] }) { return found }
        let made = parse(item, engine: engine)
        cache.withLock { $0[item.fingerprint] = made }
        return made
    }

    private static func parse(_ item: LibraryItem, engine: Engine) -> Digest? {
        let save = item.save
        let block = save.body
        let serial = SaveName.normalize(SaveName(save.rawName).serial)

        if FFT.matches(save),
           let found = FFT.overview(block, data: engine.fft, growth: engine.fftGrowth) {
            return fromFFT(found)
        }
        if FF9.matches(save), let found = FF9.overview(block, data: engine.ff9) {
            return fromFF9(found)
        }
        if FF8.isFF8(block),
           let found = FF8.overview(block, region: item.info.region,
                                    data: engine.ff8, tables: engine.ff8Tables) {
            return fromFF8(found)
        }
        if SotN.matches(save), let found = SotN.overview(block, data: engine.sotn) {
            return fromSotN(found)
        }
        if FF6.matches(save), let found = FF6.overview(block, data: engine.ff6) {
            return fromFF6(found)
        }
        if FF5.matches(save), let found = FF5.overview(block, data: engine.ff5) {
            return fromFF5(found)
        }
        if RE1.matches(save), let found = RE1.overview(block, data: engine.re1) {
            return fromRE1(found)
        }
        if FF7.matches(save), let found = FF7.overview(block, data: engine.ff7) {
            return fromFF7(found)
        }
        if Vagrant.matches(save), let found = Vagrant.overview(block) {
            return fromVagrant(found)
        }
        if ParasiteEve2.matches(save), let found = ParasiteEve2.overview(block) {
            return fromPE2(found, signature: item.signature)
        }
        if Crash2.matches(save), let found = Crash2.overview(block) {
            return fromCrash2(found)
        }
        if Chronicles.matches(save), let found = Chronicles.overview(block) {
            return fromChronicles(found)
        }
        // Игры без своего разборщика - общий разбор по шаблону.
        if let found = engine.templates.overview(block, serial: serial) {
            return Digest(
                game: found.game,
                playtime: nil,
                fields: found.fields.map { Field(label: $0.name, value: $0.value) },
                members: [], membersTitle: "",
                sections: found.sections.map {
                    Section(title: $0.name, items: $0.set.map {
                        Field(label: $0, value: "")
                    }, note: L.t("{0} of {1}", $0.set.count, $0.total))
                })
        }
        return nil
    }

    // MARK: - по играм

    static func fromVagrant(_ found: Vagrant.Overview) -> Digest {
        // Шесть классов противников - порядок из `vs_main_scoredata_t`.
        let classes = [L.t("Humans"), L.t("Beasts"), L.t("Undead"), L.t("Phantoms"), L.t("Dragons"), L.t("Evils")]
        var sections: [Section] = []

        if !found.weapons.isEmpty {
            sections.append(Section(
                title: L.t("Weapons carried"),
                items: found.weapons.map { Field(label: $0, value: "") }))
        }
        if !found.storedWeapons.isEmpty {
            sections.append(Section(
                title: L.t("Weapons in container"),
                items: found.storedWeapons.map { Field(label: $0, value: "") }))
        }
        // Названия предметов вместо занятых мест: «Cure Potion x4»
        // говорит больше, чем «Прочее 28 из 64».
        for section in Vagrant.carried where section.kind != "weapons" {
            if let list = found.carriedItems[section.kind], !list.isEmpty {
                sections.append(Section(
                    title: L.t("Carried — {0}", section.name),
                    items: list.map {
                        Field(label: $0.name,
                              value: $0.used > 1 ? "\($0.used)" : "")
                    }))
            }
        }
        for section in Vagrant.stored where section.kind != "weapons" {
            if let list = found.storedItems[section.kind], !list.isEmpty {
                sections.append(Section(
                    title: L.t("Container — {0}", section.name),
                    items: list.map {
                        Field(label: $0.name,
                              value: $0.used > 1 ? "\($0.used)" : "")
                    }))
            }
        }

        sections.append(Section(
            title: L.t("Carried"),
            items: found.carried.map {
                Field(label: $0.name, value: L.t("{0} of {1}", $0.used, $0.total))
            }))
        sections.append(Section(
            title: L.t("In container"),
            items: found.stored.map {
                Field(label: $0.name, value: L.t("{0} of {1}", $0.used, $0.total))
            }))
        // Освоенное - по видам, с названиями из самой игры.
        for (key, title) in [("breakArt", L.t("Break Arts")),
                             ("spell", L.t("Spells")),
                             ("ability", L.t("Abilities"))] {
            if let list = found.learned[key], !list.isEmpty {
                sections.append(Section(
                    title: title,
                    items: list.map { Field(label: $0, value: "") },
                    note: "\(list.count)"))
            }
        }

        if !found.unopened.isEmpty {
            sections.append(Section(
                title: L.t("Rooms not found"),
                items: found.unopened.map {
                    Field(label: $0.name, value: String($0.used))
                },
                note: L.t("{0} total", found.unopened.reduce(0) { $0 + $1.used })))
        }
        sections.append(Section(
            title: L.t("Killed"),
            items: zip(classes, found.kills).map {
                Field(label: $0.0, value: number($0.1))
            },
            note: L.t("{0} total", number(found.kills.reduce(0, +)))))

        return Digest(
            game: "Vagrant Story",
            playtime: found.playtimeRaw,
            fields: [
                Field(label: L.t("Playtime"), value: time(found.playtime)),
                Field(label: "HP", value: "\(found.hp[0])/\(found.hp[1])"),
                Field(label: "MP", value: "\(found.mp[0])/\(found.mp[1])"),
                Field(label: L.t("Map explored"), value: "\(found.mapCompletion) %"),
                // Знаменатель - из самой игры, а не прикидка: процент
                // она считает как rooms * 100 / 361.
                Field(label: L.t("Rooms found"),
                      value: L.t("{0} of {1}", found.rooms, Vagrant.roomsTotal)),
                Field(label: L.t("Rooms left"),
                      value: String(max(0, Vagrant.roomsTotal - found.rooms))),
                Field(label: L.t("Chests opened"), value: String(found.chests)),
                Field(label: L.t("Arts learned"),
                      value: "\(found.artsLearned) из 48"),
                Field(label: L.t("Abilities unlocked"), value: String(found.abilities)),
                Field(label: L.t("Longest chain"), value: String(found.maxChain)),
                Field(label: L.t("Heals"), value: String(found.heals)),
                Field(label: L.t("Actions learned"), value: String(found.actions)),
                Field(label: L.t("Maps explored"), value: String(found.maps)),
                Field(label: L.t("Times cleared"), value: String(found.clearCount)),
                Field(label: L.t("Saves total"), value: String(found.savesTotal)),
                Field(label: L.t("Saves this run"), value: String(found.savesGame)),
                Field(label: L.t("Location"), value: String(found.location)),
            ],
            members: [], membersTitle: "", sections: sections)
    }

    static func fromChronicles(_ found: Chronicles.Overview) -> Digest {
        Digest(
            game: "Castlevania Chronicles",
            playtime: nil,
            fields: [
                Field(label: L.t("Player"), value: found.name),
                Field(label: L.t("Stage"), value: String(format: "%02d", found.stage)),
                Field(label: L.t("Level"), value: String(found.level)),
                // Второе число с экрана выбора: что оно значит - неизвестно,
                // поэтому и подписано тем, чем оно является на экране.
                Field(label: L.t("Second number"),
                      value: String(format: "%02d", found.counter)),
                Field(label: L.t("Saved"), value: found.saved),
            ],
            members: [], membersTitle: "", sections: [])
    }

    static func fromCrash2(_ found: Crash2.Overview) -> Digest {
        Digest(
            game: "Crash Bandicoot 2",
            playtime: nil,
            fields: [
                Field(label: L.t("Player"), value: found.name.isEmpty ? "—" : found.name),
                Field(label: L.t("Level"), value: String(found.level)),
                Field(label: L.t("Lives"), value: String(found.lives)),
                Field(label: L.t("Fruit"), value: String(found.wumpa)),
                Field(label: L.t("Aku Aku"), value: String(found.akuAku)),
                Field(label: L.t("Crystals"), value: String(found.crystals)),
                Field(label: L.t("Gems@@count"), value: String(found.gems)),
                Field(label: L.t("Levels cleared"), value: String(found.progress)),
                Field(label: L.t("Secrets"), value: String(found.secrets)),
            ],
            members: [], membersTitle: "", sections: [])
    }

    static func fromPE2(_ found: ParasiteEve2.Overview,
                        signature: String) -> Digest {
        // Место берём из подписи: справочника локаций в разборе нет,
        // а игра пишет название сама.
        let place = signature
            .drop(while: { $0 != " " }).drop(while: { $0 == " " })
            .drop(while: { $0 != " " }).trimmingCharacters(in: .whitespaces)
        return Digest(
            game: "Parasite Eve II",
            playtime: found.playtimeMinutes * 60,
            fields: [
                Field(label: L.t("Playtime"),
                      value: String(format: "%d:%02d",
                                    found.playtime[0], found.playtime[1])),
                Field(label: L.t("Place"), value: place.isEmpty ? "—" : place),
                Field(label: L.t("Items carried"), value: String(found.items)),
                Field(label: L.t("In storage"), value: String(found.stored)),
                Field(label: L.t("Records in block"), value: String(found.banks)),
            ],
            members: [], membersTitle: "", sections: [])
    }

    static func fromFFT(_ found: FFT.Overview) -> Digest {
        let labels = ["hp": "HP", "mp": "MP", "sp": L.t("speed"),
                      "pa": L.t("p.atk"), "ma": L.t("m.atk")]
        let order = ["hp", "mp", "sp", "pa", "ma"]
        return Digest(
            game: "Final Fantasy Tactics",
            playtime: total(found.playtime),
            fields: [
                Field(label: L.t("Hero"), value: found.name),
                Field(label: L.t("Class"), value: found.job),
                Field(label: L.t("Level"), value: String(found.level)),
                Field(label: L.t("Playtime"), value: time(found.playtime)),
                Field(label: L.t("Funds"), value: L.t("{0} gil", number(found.funds))),
                Field(label: L.t("Place"), value: found.location),
                Field(label: L.t("In-game date"),
                      value: found.date.joined(separator: " ")),
                Field(label: L.t("Birthday"),
                      value: found.birthday.joined(separator: " ")),
            ],
            members: found.units.map { unit in
                var extra = [unit.who, unit.gender, unit.zodiac]
                if unit.guest { extra.append(L.t("guest")) }
                if !unit.status.isEmpty { extra.append(unit.status) }
                // У монстров класс один и сменить его нельзя, поэтому
                // экранных статов для них не существует - только сырые.
                let numbers = order.compactMap { key -> Field? in
                    guard let value = unit.stats[key] else { return nil }
                    return Field(label: labels[key] ?? key, value: String(value))
                }
                return Member(
                    name: unit.name.isEmpty ? unit.who : unit.name,
                    role: unit.job,
                    level: String(unit.level),
                    stats: numbers + [
                        Field(label: L.t("brave"), value: String(unit.brave)),
                        Field(label: L.t("faith"), value: String(unit.faith)),
                    ],
                    gear: unit.gear.compactMap { $0.count > 1 ? $0[1] : nil },
                    extra: extra.filter { !$0.isEmpty }.joined(separator: " · "))
            },
            membersTitle: L.t("Party@@squad"),
            sections: [
                Section(title: L.t("Inventory"), items: pairs(found.inventory),
                        note: L.t("{0} entries", found.inventory.count)),
            ])
    }

    static func fromFF9(_ found: FF9.Overview) -> Digest {
        var fields = [
            Field(label: L.t("Playtime"), value: time(found.playtime)),
            Field(label: L.t("Gil"), value: number(found.gil)),
            Field(label: L.t("Location"), value: String(found.location)),
        ]
        if let disc = found.disc {
            fields.insert(Field(label: L.t("Disc"), value: String(disc)), at: 0)
        }
        return Digest(
            game: "Final Fantasy IX",
            playtime: total(found.playtime),
            fields: fields,
            members: found.party.map { unit in
                Member(name: unit.name.isEmpty ? unit.who : unit.name,
                       role: unit.who,
                       level: String(unit.level),
                       stats: [
                           Field(label: "HP", value: "\(unit.hp[0])/\(unit.hp[1])"),
                           Field(label: "MP", value: "\(unit.mp[0])/\(unit.mp[1])"),
                           Field(label: L.t("exp"), value: number(unit.exp)),
                       ],
                       gear: unit.gear.compactMap { $0.count > 1 ? $0[1] : nil },
                       extra: unit.trance > 0 ? L.t("trance {0}", unit.trance) : "")
            },
            membersTitle: L.t("Party"),
            sections: [
                Section(title: L.t("Inventory"), items: pairs(found.inventory),
                        note: L.t("{0} entries", found.inventory.count)),
            ])
    }

    static func fromFF8(_ found: FF8.Overview) -> Digest {
        let chosen = found.playtime.matches ?? "as_seconds"
        let parts = chosen == "as_ticks" ? found.playtime.asTicks
                                         : found.playtime.asSeconds
        // Заголовок игры упирается в 99:59, а счётчик растёт дальше -
        // показываем счётчик. Про потолок не пишем: подпись видна в шапке.
        let value = String(format: "%d:%02d:%02d",
                           parts["hours"] ?? 0, parts["minutes"] ?? 0,
                           parts["seconds"] ?? 0)

        let statNames = [L.t("Strength"), L.t("Vitality"), L.t("Magic"), L.t("Spirit"), L.t("Agility"), L.t("Luck")]
        let party = found.characters.filter(\.exists).map { who in
            Member(name: who.name.isEmpty ? "—" : who.name,
                   role: who.weapon,
                   level: String(who.level),
                   stats: [Field(label: "HP", value: "\(who.hp)/\(who.hpMax)")]
                       + zip(statNames, who.stats).map {
                           Field(label: $0.0.lowercased(), value: String($0.1))
                       },
                   gear: who.magic.compactMap { row in
                       row.count > 1 ? "\(row[0]) ×\(row[1])" : row.first
                   },
                   extra: L.t("kills {0} · GF {1}", who.kills, who.gfs))
        }
        // Гардианы - половина смысла сейва FF8, без них панель бессмысленна.
        let guardians = found.guardians.filter(\.exists).map { gf in
            Member(name: gf.name,
                   role: L.t("{0} of {1} abilities", gf.learned.count, gf.totalSlots),
                   level: String(gf.level),
                   stats: [Field(label: "HP", value: String(gf.hp)),
                           Field(label: L.t("kills"), value: String(gf.kills))],
                   gear: gf.learned,
                   extra: gf.learning.isEmpty ? ""
                       : L.t("learns: ") + gf.learning.compactMap { row in
                           row.count > 2 ? "\(row[0]) \(row[1])/\(row[2])" : row.first
                       }.joined(separator: ", "))
        }
        return Digest(
            game: "Final Fantasy VIII",
            playtime: (parts["hours"] ?? 0) * 3600 + (parts["minutes"] ?? 0) * 60
                + (parts["seconds"] ?? 0),
            fields: [
                Field(label: L.t("Playtime"), value: value),
                Field(label: L.t("Gil"), value: number(found.gils)),
                Field(label: L.t("Steps"), value: number(found.steps)),
                Field(label: L.t("Battles"), value: number(found.battles)),
                Field(label: L.t("In party"), value: found.party.joined(separator: ", ")),
            ],
            members: party,
            membersTitle: L.t("Characters"),
            sections: [
                Section(title: L.t("Guardians"),
                        items: guardians.map {
                            Field(label: $0.name, value: L.t("lv. {0} · {1}", $0.level, $0.role))
                        },
                        note: L.t("{0} of 16", guardians.count)),
                Section(title: L.t("Inventory"), items: pairs(found.items),
                        note: L.t("{0} entries", found.items.count)),
            ])
    }

    static func fromSotN(_ found: SotN.Overview) -> Digest {
        Digest(
            game: "Castlevania: Symphony of the Night",
            playtime: total(found.playtime.map(Int.init)),
            fields: [
                Field(label: L.t("Hero"), value: found.character),
                Field(label: L.t("Level"), value: String(found.level)),
                Field(label: L.t("Playtime"), value: time(found.playtime.map(Int.init))),
                Field(label: L.t("Map"), value: String(format: "%.2f %%", found.map)),
                Field(label: "HP", value: "\(found.hp[0])/\(found.hp[1])"),
                Field(label: "MP", value: "\(found.mp[0])/\(found.mp[1])"),
                Field(label: L.t("Hearts"), value: "\(found.hearts[0])/\(found.hearts[1])"),
                Field(label: L.t("Experience"), value: number(found.exp)),
                Field(label: L.t("Gold"), value: number(found.gold)),
                Field(label: L.t("Kills"), value: number(found.kills)),
                Field(label: L.t("Location"), value: String(found.location)),
                Field(label: L.t("Progress"), value: String(found.progression)),
            ],
            members: found.familiars.map { row in
                Member(name: row.first ?? "",
                       role: L.t("familiar"),
                       level: row.count > 1 ? row[1] : "",
                       stats: row.count > 2 ? [Field(label: L.t("exp"), value: row[2])] : [])
            },
            membersTitle: L.t("Familiars"),
            sections: [
                Section(title: L.t("Equipment"),
                        items: found.gear.compactMap { row in
                            row.count > 1 ? Field(label: row[1], value: row[0]) : nil
                        }),
                Section(title: L.t("Relics"),
                        items: found.relics.map { Field(label: $0, value: "") },
                        note: String(found.relics.count)),
                Section(title: L.t("Spells"),
                        items: found.spells.map { Field(label: $0, value: "") },
                        note: String(found.spells.count)),
                Section(title: L.t("Inventory"), items: pairs(found.inventory),
                        note: L.t("{0} entries", found.inventory.count)),
                Section(title: L.t("Bestiary"),
                        items: found.bestiary.map { Field(label: $0, value: "") },
                        note: L.t("{0} of {1}", found.bestiary.count, found.enemyTotal)),
                Section(title: L.t("With drop"),
                        items: found.drops.map { Field(label: $0, value: "") },
                        note: String(found.drops.count)),
            ])
    }

    static func fromFF6(_ found: FF6.Overview) -> Digest {
        Digest(
            game: "Final Fantasy VI",
            playtime: total(found.playtime),
            fields: [
                Field(label: L.t("Playtime"), value: time(found.playtime)),
                Field(label: L.t("Gil"), value: number(found.gil)),
                Field(label: L.t("Steps"), value: number(found.steps)),
                Field(label: L.t("Saves"), value: String(found.saves)),
                Field(label: L.t("Place"), value: found.location),
                Field(label: L.t("Not recruited"), value: String(found.notRecruited)),
            ],
            members: found.party.map { unit in
                let learned = unit.magic.filter(\.learned).count
                return Member(
                    name: unit.name,
                    role: unit.who,
                    level: String(unit.level),
                    stats: [
                        Field(label: "HP", value: "\(unit.hp[0])/\(unit.hp[1])"),
                        Field(label: "MP", value: "\(unit.mp[0])/\(unit.mp[1])"),
                        Field(label: L.t("exp"), value: number(unit.exp)),
                    ],
                    gear: unit.gear.compactMap { $0.count > 1 ? $0[1] : nil }
                        + unit.magic.filter { !$0.learned }.map {
                            "\($0.name) \($0.percent) %"
                        },
                    extra: ([unit.abilities.joined(separator: ", ")]
                        + (unit.magic.isEmpty ? []
                           : [L.t("magic {0} of {1}", learned, unit.magic.count)]))
                        .filter { !$0.isEmpty }.joined(separator: " · "))
            },
            membersTitle: L.t("Party"),
            sections: [
                Section(title: L.t("Espers"),
                        items: found.espers.map { Field(label: $0, value: "") },
                        note: String(found.espers.count)),
                Section(title: L.t("Inventory"), items: pairs(found.inventory),
                        note: L.t("{0} entries", found.inventory.count)),
            ])
    }

    static func fromFF5(_ found: FF5.Overview) -> Digest {
        Digest(
            game: "Final Fantasy V",
            playtime: total(found.playtime),
            fields: [
                Field(label: L.t("Playtime"), value: time(found.playtime)),
                Field(label: L.t("Gil"), value: number(found.money)),
                Field(label: L.t("Battles"), value: number(found.battles)),
                Field(label: L.t("Killed"), value: number(found.kills)),
                Field(label: L.t("Saves"), value: String(found.saves)),
                Field(label: L.t("Chests opened"), value: String(found.chests)),
                Field(label: L.t("World"), value: String(found.world)),
                Field(label: L.t("Map"), value: String(found.map)),
                Field(label: L.t("Roster"),
                      value: found.roster.joined(separator: ", ")),
            ],
            members: found.party.map { unit in
                Member(name: unit.name,
                       role: unit.job,
                       level: String(unit.level),
                       stats: [
                           Field(label: "HP", value: "\(unit.hp[0])/\(unit.hp[1])"),
                           Field(label: "MP", value: "\(unit.mp[0])/\(unit.mp[1])"),
                           Field(label: "ABP", value: String(unit.abp)),
                       ],
                       gear: unit.gear.compactMap { $0.count > 1 ? $0[1] : nil },
                       extra: L.t("job level {0}", unit.jobLevel))
            },
            membersTitle: L.t("Party"),
            sections: [
                Section(title: L.t("Inventory"), items: pairs(found.inventory),
                        note: L.t("{0} entries", found.inventory.count)),
            ])
    }

    static func fromRE1(_ found: RE1.Overview) -> Digest {
        Digest(
            game: "Resident Evil",
            playtime: nil,
            fields: [
                Field(label: L.t("Hero"), value: found.character),
                Field(label: L.t("Health"), value: String(found.health)),
                Field(label: L.t("Place"), value: found.location),
                Field(label: L.t("Ink ribbons"), value: String(found.inkRibbons)),
                Field(label: L.t("Time counter"), value: number(found.playtimeRaw)),
                Field(label: L.t("If these are seconds"),
                      value: time([Int(found.playtimeRaw) / 3600,
                                   Int(found.playtimeRaw) / 60 % 60,
                                   Int(found.playtimeRaw) % 60])),
            ],
            members: [], membersTitle: "",
            sections: [
                Section(title: L.t("Carried"), items: pairs(found.inventory),
                        note: L.t("{0} of 8", found.inventory.count)),
                Section(title: L.t("In container"), items: pairs(found.container),
                        note: L.t("{0} entries", found.container.count)),
            ])
    }

    static func fromFF7(_ found: FF7.Overview) -> Digest {
        let statNames = [L.t("str"), L.t("vit"), L.t("magic"), L.t("spr"), L.t("agi"), L.t("luck")]
        return Digest(
            game: "Final Fantasy VII",
            playtime: total(found.playtime),
            fields: [
                Field(label: L.t("Hero"), value: found.leader),
                Field(label: L.t("Level"), value: String(found.level)),
                Field(label: L.t("Playtime"), value: time(found.playtime)),
                Field(label: L.t("Gil"), value: number(found.gil)),
                Field(label: L.t("Place"), value: found.location),
                Field(label: L.t("Slot"), value: found.locationText),
                Field(label: L.t("Battles"), value: number(found.battles)),
                Field(label: L.t("Escapes"), value: number(found.runs)),
            ],
            members: found.characters.map { who in
                Member(name: who.name.isEmpty ? who.who : who.name,
                       role: who.who,
                       level: String(who.level),
                       stats: [Field(label: "HP", value: "\(who.hp[0])/\(who.hp[1])")]
                           + zip(statNames, who.stats).map {
                               Field(label: $0.0, value: String($0.1))
                           },
                       // Экипировка адресуется своими списками, а не общим
                       // инвентарём - иначе Клауд оказывается вооружён зельем.
                       gear: [who.weapon, who.armor, who.accessory]
                           .filter { !$0.isEmpty },
                       extra: who.materia.isEmpty ? ""
                           : L.t("materia: ") + who.materia.map(\.materia.name)
                               .joined(separator: ", "))
            },
            membersTitle: L.t("Characters"),
            sections: [
                Section(title: L.t("Materia"),
                        items: found.materia.map {
                            Field(label: $0.name,
                                  value: $0.mastered ? L.t("mastered")
                                                     : "\($0.stars)/\($0.total)")
                        },
                        note: String(found.materia.count)),
                Section(title: L.t("Stolen by Yuffie"),
                        items: found.materiaStolen.map {
                            Field(label: $0.name,
                                  value: $0.mastered ? L.t("mastered")
                                                     : "\($0.stars)/\($0.total)")
                        },
                        note: String(found.materiaStolen.count)),
                Section(title: L.t("Inventory"),
                        items: found.inventory.map {
                            Field(label: $0.name, value: String($0.count))
                        },
                        note: L.t("{0} entries", found.inventory.count)),
            ])
    }
}
