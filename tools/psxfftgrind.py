#!/usr/bin/env python3
"""Солвер паверлевелинга Final Fantasy Tactics.

Считает, сколько циклов level down -> level up и в каком порядке нужно
прогнать, чтобы вывести статы бойца на потолок.

По FFT-STAT-CALC-SPEC.md §6. Приближение по замкнутой форме используется
только для верхней границы перебора; сам ответ ищется точной целочисленной
симуляцией, иначе оптимум теряется - float-модель отбрасывает верные планы,
потому что игнорирует поуровневое округление.
"""

import itertools
import math
import re

import psxfftstats as stats

TOP_LEVEL = 99
BOTTOM_LEVEL = 1

# На спуске выгоден класс с худшим ростом - тогда теряется меньше всего.
# Bard мужской, Dancer женский, третьего не дано.
DOWN_JOBS = {"мужской": "Bard", "женский": "Dancer"}
# Единственные классы, пробивающие базовую планку роста хоть по одному стату.
UP_JOBS = ("Mime", "Ninja", "Summoner")


def special_job_for(owner, data):
    """Сюжетный класс бойца: в справочнике они подписаны владельцем в скобках,
    например "Dragoner (Reis)". Возвращает только тот, что реально обгоняет
    дженериков хоть по одному стату - остальные брать смысла нет."""
    if not owner:
        return None
    who = owner.split()[0]
    generics = [j for j in data["generic_jobs"] if not j.get("wotl_only")]
    best = {s: min(j["growth"][s] for j in generics) for s in stats.STATS}
    for job in data["special_jobs"]:
        found = re.search(r"\(([^)]+)\)", job["name"])
        if not found or found.group(1).split()[0] != who:
            continue
        if any(job["growth"][s] < best[s] for s in stats.STATS):
            return job
    return None


def by_name(table, name):
    for job in table.values():
        if job["name"] == name:
            return job
    raise KeyError(name)


def cycle_multiplier(down, up, stat, top=TOP_LEVEL):
    """Во сколько раз меняется raw за цикл top -> 1 -> top (замкнутая форма)."""
    cu, cd = up["growth"][stat], down["growth"][stat]
    return ((cu + top) / (cu + 1)) * (cd / (cd + top - 1))


def run_cycle(raw, down, up, stat, top=TOP_LEVEL):
    """Точный цикл: спуск в одном классе, подъём в другом."""
    value = stats.run_down(raw, down["growth"][stat], top, BOTTOM_LEVEL)
    return stats.run_up(value, up["growth"][stat], BOTTOM_LEVEL, top)


def step(raw, down, up, top=TOP_LEVEL):
    return {s: run_cycle(raw[s], down, up, s, top) for s in stats.STATS}


def simulate(start, blocks, down, top=TOP_LEVEL):
    """blocks - [(класс подъёма, число циклов)] по порядку."""
    raw = dict(start)
    for up, count in blocks:
        for _ in range(count):
            raw = step(raw, down, up, top)
    return raw


def meets(raw, goals):
    return all(raw[stat] >= goals[stat] for stat in stats.STATS)


SLACK = 8


def _bounds(start, goals, down, ups, top, limit):
    """Верхняя граница числа циклов на блок.

    Считать блоки независимо нельзя: у части связок множитель меньше единицы
    (цикл ниндзи и призывателя точит MA, цикл мима съедает MP), поэтому
    блок-донор должен отработать лишние циклы поверх собственной оценки.
    Запас SLACK это покрывает - без него солвер не находит решения там,
    где оно есть."""
    out = []
    for up in ups:
        worst = 0
        for stat in stats.STATS:
            if start[stat] >= goals[stat]:
                continue
            mult = cycle_multiplier(down, up, stat, top)
            if mult <= 1.0:
                continue
            worst = max(worst, math.ceil(
                math.log(goals[stat] / start[stat]) / math.log(mult)))
        out.append(min(limit, worst + SLACK) if worst else 0)
    return out


def _remaining_min(raw, goals, down, ups, top):
    """Нижняя оценка: сколько циклов минимум ещё нужно.

    Для каждого недотянутого стата берём самый быстрый из оставшихся классов
    и считаем, сколько циклов он потребует в одиночку. Ответ - максимум по
    статам: меньше этого числа физически не выйдет, значит ветку можно резать
    не доходя до конца."""
    need = 0
    for stat in stats.STATS:
        if raw[stat] >= goals[stat]:
            continue
        best_mult = max((cycle_multiplier(down, up, stat, top) for up in ups),
                        default=1.0)
        if best_mult <= 1.0:
            return math.inf
        need = max(need, math.ceil(
            math.log(goals[stat] / raw[stat]) / math.log(best_mult)))
    return need


def _search(start, goals, down, ups, bounds, top, ceiling):
    """Перебор с инкрементальной симуляцией.

    Каждый следующий цикл считается от предыдущего состояния, а не пересчётом
    всего плана заново - иначе перебор не укладывается в разумное время.
    """
    best = None

    def walk(depth, raw, taken, used):
        nonlocal best
        limit_total = best[0] if best else ceiling
        if used >= limit_total:
            return
        if used + _remaining_min(raw, goals, down, ups[depth:], top) >= limit_total:
            return
        if depth == len(ups):
            if meets(raw, goals):
                best = (used, list(taken), raw)
            return
        state = raw
        last = depth == len(ups) - 1
        for count in range(0, bounds[depth] + 1):
            if count:
                state = step(state, down, ups[depth], top)
            if used + count >= (best[0] if best else ceiling):
                break
            walk(depth + 1, state, taken + [(ups[depth], count)], used + count)
            # На последнем блоке первое же выполнение целей и есть минимум:
            # дальше счётчик только растёт, смысла продолжать нет.
            if last and meets(state, goals):
                break

    walk(0, start, [], 0)
    return best


def _solve_with(start, goals, down, ups, top, limit, ceiling):
    """Минимум по всем перестановкам блоков при заданном стартовом потолке."""
    best = None
    for order in itertools.permutations(ups):
        found = _search(start, goals, down, list(order),
                        _bounds(start, goals, down, list(order), top, limit),
                        top, ceiling)
        if found and found[0] < ceiling:
            ceiling = found[0]
            best = found
    return best


def _pack(found, down, goals):
    return {"blocks": [(u["name"], c) for u, c in found[1] if c],
            "total": found[0], "final": found[2],
            "down": down["name"], "goals": goals}


def solve(start, gender, goals=None, top=TOP_LEVEL, limit=40, data=None,
          up_jobs=None, owner=None):
    """Минимальный проверенный план или None.

    start    - raw-статы, dict по stats.STATS
    gender   - "мужской" / "женский"
    up_jobs  - имена классов подъёма; по умолчанию Mime/Ninja/Summoner.
    owner    - кто это по сюжету ("Reis", "Cloud"). Если у бойца есть личный
               класс с лучшим ростом, он добавляется в перебор автоматически.
    """
    data = data or stats.load()
    table = stats.job_table(data)
    goals = goals or data["functional_raw_caps"]
    goals = {s: goals[s] for s in stats.STATS}

    if gender not in DOWN_JOBS:
        return None
    down = by_name(table, DOWN_JOBS[gender])
    ups = [by_name(table, name) for name in (up_jobs or UP_JOBS)]

    if meets(start, goals):
        return {"blocks": [], "total": 0, "final": dict(start),
                "down": down["name"], "goals": goals}

    personal = special_job_for(owner, data) if up_jobs is None else None
    seed = None
    if personal is not None:
        # Сначала дешёвое решение на дженериках: его длина становится стартовым
        # потолком для перебора с четвёртым классом. Без этого DFS почти не
        # отсекается и считает минутами вместо секунд.
        seed = _solve_with(start, goals, down, ups, top, limit,
                           limit * len(ups) + 1)
        ups = ups + [personal]

    ceiling = seed[0] if seed else limit * len(ups) + 1
    best = _pack(seed, down, goals) if seed else None
    # Порядок блоков не бесплатен: мим съедает 29.5 % MP за цикл, поэтому его
    # блок обязан идти раньше призывателя. Перебираем перестановки честно.
    found = _solve_with(start, goals, down, ups, top, limit, ceiling)
    return _pack(found, down, goals) if found else best


def describe(plan, start, indent=""):
    if plan is None:
        return f"{indent}решение не найдено в заданных пределах"
    if not plan["blocks"]:
        return f"{indent}все статы уже на потолке, гринд не нужен"
    goals = plan["goals"]
    lines = [f"{indent}спуск в классе {plan['down']}, циклов всего: {plan['total']}"]
    for name, count in plan["blocks"]:
        lines.append(f"{indent}  {count:>3} × подъём {name}")
    for stat in stats.STATS:
        mark = "" if plan["final"][stat] >= goals[stat] else "  НЕ ДОТЯНУЛ"
        lines.append(f"{indent}  {stats.STAT_LABELS[stat]:<12}"
                     f" {start[stat]:>9} → {plan['final'][stat]:>9}"
                     f"   цель {goals[stat]:>9}{mark}")
    return "\n".join(lines)
