#!/usr/bin/env python3
"""Генератор файла projects.planner (SQLite) для GNOME Planner.

Задачи ВКР «Crystal Lattice Visualization» (см. Note.md, раздел «5. Задачи»)
преобразуются в задачи/подзадачи с датами начала и окончания, чтобы в
приложении GNOME Planner их можно было просмотреть на диаграмме Ганта.

Формат соответствует схеме GNOME Planner (проверено на planner 3.x / libplanner).
"""

import datetime as dt
import os
import sqlite3

# ---------------------------------------------------------------------------
# Параметры проекта
# ---------------------------------------------------------------------------

PROJECT_NAME = "Crystal Lattice Visualization (ВКР)"
PROJECT_DESCRIPTION = (
    "Веб-приложение для интерактивной 3D-визуализации кристаллических "
    "решёток с интеллектуальным анализом на основе машинного обучения."
)
PROJECT_ORG = "ВКР"
PROJECT_START = dt.date(2026, 2, 2)   # понедельник
PROJECT_FINISH = dt.date(2026, 5, 15)

MS_PER_DAY = 86_400_000


def day(d: dt.date) -> int:
    """Дата -> миллисекунды от эпохи (полночь UTC), как хранит Planner."""
    return int(dt.datetime(d.year, d.month, d.day).timestamp() * 1000)


def add_days(d: dt.date, n: int) -> dt.date:
    return d + dt.timedelta(days=n)


# ---------------------------------------------------------------------------
# Дерево задач: (id, parent_id, name, start, finish, work_percentage, type)
# id <= 7 — summary-задачи (7 основных задач); далее — подзадачи (уровень 2).
# ---------------------------------------------------------------------------

TASKS = [
    # Задача 1 — визуализация решёток
    (1, None, "1. Визуализировать кристаллические решётки (FCC, BCC, SC, Diamond, HCP) типовых элементов в интерактивном 3D",
     "2026-02-02", "2026-02-27", 100, "standard"),
    (11, 1, "1.1. Генератор unit-ячеек по типу решётки и параметру элемента", "2026-02-02", "2026-02-05", 100, "standard"),
    (12, 1, "1.2. Построение суперъячеек n×n×n с учётом периодичности", "2026-02-05", "2026-02-09", 100, "standard"),
    (13, 1, "1.3. Справочные данные: ковалентные радиусы, цвета CPK, типы решёток", "2026-02-02", "2026-02-04", 100, "standard"),
    (14, 1, "1.4. Интерактивная 3D-сцена: вращение, масштабирование, орбита камеры", "2026-02-09", "2026-02-13", 100, "standard"),
    (15, 1, "1.5. Атомы как сферы с настраиваемым размером и цветом по элементу", "2026-02-13", "2026-02-17", 100, "standard"),
    (16, 1, "1.6. Межатомные связи как цилиндры между близкими парами атомов", "2026-02-17", "2026-02-20", 100, "standard"),
    (17, 1, "1.7. Инструмент плоскости среза (slice)", "2026-02-20", "2026-02-23", 100, "standard"),
    (18, 1, "1.8. Панель параметров: элемент, тип решётки, суперъячейка, фон", "2026-02-23", "2026-02-25", 100, "standard"),
    (19, 1, "1.9. Проверка корректности геометрии (координационные числа, расстояния)", "2026-02-25", "2026-02-27", 100, "standard"),

    # Задача 2 — смешанные системы
    (2, None, "2. Адаптировать веб-приложение для работы со смешанными системами (Ni–Al, Ti–Al)",
     "2026-02-27", "2026-03-13", 100, "standard"),
    (21, 2, "2.1. Подстановка атомов одного элемента в узлы решётки другого (/api/substitute)", "2026-02-27", "2026-03-02", 100, "standard"),
    (22, 2, "2.2. Выбор сайтов замещения (/api/sites) в интерфейсе", "2026-03-02", "2026-03-04", 100, "standard"),
    (23, 2, "2.3. Стехиометрия смешанной системы (доля замещений, упорядоченность)", "2026-03-04", "2026-03-06", 100, "standard"),
    (24, 2, "2.4. Случайный и детерминированный режимы замещения (seed)", "2026-03-06", "2026-03-09", 100, "standard"),
    (25, 2, "2.5. Признаки модели: разная «химия связи» для разных пар элементов", "2026-03-09", "2026-03-11", 100, "standard"),
    (26, 2, "2.6. Проверка предсказания связей на модельных системах Ni–Al и Ti–Al", "2026-03-11", "2026-03-13", 100, "standard"),
    (27, 2, "2.7. Визуальное различение элементов по цвету и подписи атомов", "2026-03-09", "2026-03-11", 100, "standard"),

    # Задача 3 — обучение ИИ-модели
    (3, None, "3. Реализовать создание ИИ-модели в веб-приложении путём загрузки обучающей выборки",
     "2026-03-13", "2026-04-03", 100, "standard"),
    (31, 3, "3.1. Формат обучающей выборки (пары атомов, признаки, метка связи)", "2026-03-13", "2026-03-16", 100, "standard"),
    (32, 3, "3.2. Endpoint загрузки выборки и валидации формата", "2026-03-16", "2026-03-19", 100, "standard"),
    (33, 3, "3.3. Предобработка: нормировка признаков, разбиение train/test", "2026-03-19", "2026-03-23", 100, "standard"),
    (34, 3, "3.4. Архитектура модели (слои, активации, размер скрытых слоёв)", "2026-03-23", "2026-03-26", 100, "standard"),
    (35, 3, "3.5. Цикл обучения (эпохи, метрики, сохранение весов)", "2026-03-26", "2026-03-30", 100, "standard"),
    (36, 3, "3.6. Автотренировка базовой модели на синтетических данных", "2026-03-30", "2026-04-01", 100, "standard"),
    (37, 3, "3.7. Сохранение/загрузка весов модели между запусками сервера", "2026-04-01", "2026-04-03", 100, "standard"),
    (38, 3, "3.8. Отчёт о качестве обучения (/api/model_info, /api/train_model)", "2026-04-01", "2026-04-03", 100, "standard"),

    # Задача 4 — серверный модуль и API
    (4, None, "4. Разработать серверный модуль генерации атомных структур и спроектировать единый API",
     "2026-02-27", "2026-03-20", 100, "standard"),
    (41, 4, "4.1. Генерация структур на backend через ASE (bulk) для всех типов решёток", "2026-02-27", "2026-03-02", 100, "standard"),
    (42, 4, "4.2. Кэш сгенерированных структур", "2026-03-02", "2026-03-04", 100, "standard"),
    (43, 4, "4.3. Схемы запросов/ответов через Pydantic, контрактная модель данных", "2026-03-04", "2026-03-09", 100, "standard"),
    (44, 4, "4.4. Набор endpoint'ов (/api/atoms, /api/elements, /api/sites, /api/substitute, /api/predict_bonds, /api/reaction, /api/train_model, /api/model_info)",
     "2026-03-09", "2026-03-13", 100, "standard"),
    (45, 4, "4.5. CORS и раздельный запуск frontend/backend", "2026-03-13", "2026-03-15", 100, "standard"),
    (46, 4, "4.6. Обработка ошибок API и осмысленные HTTP-коды", "2026-03-15", "2026-03-18", 100, "standard"),
    (47, 4, "4.7. Нагрузочная проверка на крупных суперъячейках", "2026-03-18", "2026-03-20", 100, "standard"),

    # Задача 5 — связные компоненты графа связей
    (5, None, "5. Автоматическое выделение связных компонент графа межатомных связей («вещества», химические формулы)",
     "2026-03-20", "2026-04-03", 100, "standard"),
    (51, 5, "5.1. Построение графа связей по предсказанию (или baseline на KD-дереве)", "2026-03-20", "2026-03-23", 100, "standard"),
    (52, 5, "5.2. Поиск связных компонент алгоритмом Union-Find (detect_molecules)", "2026-03-23", "2026-03-26", 100, "standard"),
    (53, 5, "5.3. Учёт периодических границ ячейки при построении графа", "2026-03-26", "2026-03-28", 100, "standard"),
    (54, 5, "5.4. Химические формулы компонент (сортировка по холловскому порядку)", "2026-03-28", "2026-03-31", 100, "standard"),
    (55, 5, "5.5. Нумерация и фильтрация компонент по минимальному размеру", "2026-03-31", "2026-04-01", 100, "standard"),
    (56, 5, "5.6. Отображение найденных «веществ» и формул в интерфейсе", "2026-04-01", "2026-04-03", 100, "standard"),
    (57, 5, "5.7. Валидация алгоритма на эталонных структурах", "2026-04-01", "2026-04-03", 100, "standard"),

    # Задача 6 — динамика во времени
    (6, None, "6. Отображение моделирования структуры во времени с покадровой перестройкой связей",
     "2026-04-03", "2026-04-24", 100, "standard"),
    (61, 6, "6.1. Отображение статистики содержимого сцены во времени", "2026-04-03", "2026-04-07", 100, "standard"),
    (62, 6, "6.2. Плеер кадров с покадровой перемоткой в 3D-сцене", "2026-04-07", "2026-04-11", 100, "standard"),
    (63, 6, "6.3. Интерполяция позиций атомов между кадрами", "2026-04-11", "2026-04-15", 100, "standard"),
    (64, 6, "6.4. Визуализация продуктов реакции (цвета компонент, формулы по кадрам)", "2026-04-15", "2026-04-19", 100, "standard"),
    (65, 6, "6.5. Экспорт последовательности кадров (snapshot сцены)", "2026-04-19", "2026-04-22", 100, "standard"),
    (66, 6, "6.6. Оценка стабильности состава продуктов по кадрам", "2026-04-22", "2026-04-24", 100, "standard"),

    # Задача 7 — оформление и защита
    (7, None, "7. Оформление и защита работы",
     "2026-04-24", "2026-05-15", 100, "standard"),
    (71, 7, "7.1. Документация на систему и методику", "2026-04-24", "2026-04-29", 100, "standard"),
    (72, 7, "7.2. Пояснительная записка ВКР по требованиям кафедры", "2026-04-29", "2026-05-07", 100, "standard"),
    (73, 7, "7.3. Презентация для защиты", "2026-05-07", "2026-05-10", 100, "standard"),
    (74, 7, "7.4. Предзащита ВКР, учёт замечаний", "2026-05-10", "2026-05-13", 100, "standard"),
    (75, 7, "7.5. Финальные правки и защита ВКР", "2026-05-13", "2026-05-15", 100, "standard"),
]

# Зависимости finish->start между основными задачами (для логической сети
# Planner; на диаграмме Ганта показывается стрелками). Задаются как
# (последователь, предшественник) и проверяются по датам ниже.
DEPENDS = [(2, 1), (3, 2), (5, 4), (6, 5), (7, 6)]

WORK_DAYS = [day(d) for d in [
    dt.date(2026, 2, 23),  # День защитника Отечества
    dt.date(2026, 2, 24),
    dt.date(2026, 3, 9),   # Международный женский день
    dt.date(2026, 5, 1),   # Праздник Весны и Труда
    dt.date(2026, 5, 9),   # День Победы
]]

# ---------------------------------------------------------------------------
# Схема БД (совместима с libplanner)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE info (
    name TEXT NOT NULL PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE project_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    type TEXT NOT NULL,
    class TEXT NOT NULL DEFAULT 'native'
);
CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    show INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    short_name TEXT NOT NULL,
    rate DOUBLE NOT NULL,
    overtime_rate DOUBLE NOT NULL,
    units INTEGER NOT NULL,
    group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    calendar_id INTEGER REFERENCES calendars(id) ON DELETE SET NULL,
    type INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE calendars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    week_mask INTEGER NOT NULL,
    year_mask INTEGER NOT NULL,
    valid_from INTEGER NOT NULL,
    valid_to INTEGER NOT NULL,
    prev_day_mask TEXT NOT NULL,
    next_day_mask TEXT NOT NULL,
    slots_per_day INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE calendar_exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    VACATION_TYPE INTEGER NOT NULL,
    NAME TEXT NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    calendar_id INTEGER REFERENCES calendars(id) ON DELETE CASCADE
);
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type INTEGER NOT NULL DEFAULT 0,
    duration INTEGER NOT NULL,
    complete_ratio DOUBLE NOT NULL DEFAULT 0,
    start INTEGER NOT NULL,
    finish INTEGER NOT NULL,
    parent_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    notes TEXT,
    priority INTEGER NOT NULL DEFAULT 1,
    scheduled_start INTEGER,
    scheduled_finish INTEGER,
    is_milestone BOOLEAN NOT NULL DEFAULT FALSE,
    status INTEGER NOT NULL DEFAULT 0,
    cost DOUBLE NOT NULL DEFAULT 0,
    work DOUBLE NOT NULL DEFAULT 0,
    is_delayed BOOLEAN NOT NULL DEFAULT FALSE,
    is_fixed_start BOOLEAN NOT NULL DEFAULT FALSE,
    is_critical BOOLEAN NOT NULL DEFAULT FALSE,
    is_summary BOOLEAN NOT NULL DEFAULT FALSE,
    has_child BOOLEAN NOT NULL DEFAULT FALSE,
    external_id TEXT
);
CREATE TABLE task_deps (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dep_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    type INTEGER NOT NULL DEFAULT 0,
    lag INTEGER NOT NULL DEFAULT 0,
    require_full BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (task_id, dep_id)
);
CREATE TABLE links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    comment TEXT,
    type INTEGER NOT NULL DEFAULT 0,
    lag INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE assignments (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    units DOUBLE NOT NULL DEFAULT 0,
    work DOUBLE NOT NULL DEFAULT 0,
    cost DOUBLE NOT NULL DEFAULT 0,
    PRIMARY KEY (task_id, resource_id)
);
CREATE TABLE milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    time INTEGER NOT NULL,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE
);
"""

INFO_VALUES = {
    "generator": "Planner 3.26",
    "project-id": "com.gitlab.gnome.World.Planner",
    "name": PROJECT_NAME,
    "revision": "1",
    "author": "",
    "created-date-stamp": "2026-11-09T00:00:00Z",
    "vendor": "GNOME",
    "vendor-url": "https://gitlab.gnome.org/World/planner",
    "application-url": "https://gitlab.gnome.org/World/planner",
    "distribution": "packages.debian.org",
    "distribution-url": "https://packages.debian.org/stable/gnome-planner",
    "component": "planner",
    "version": "3.26",
    "title": f"{PROJECT_NAME} Project",
    "copyright": "GPL",
    "license": "GPL",
    "description": PROJECT_DESCRIPTION,
    "help-id": "planner-project-information",
    "page-properties": "[]",
    "sql-schema-version": "6",
    "default-cost-type": "1",
    "default-time-unit": "1",
    "currency": "USD",
    "currency-small-unit": "cent",
    "calendar-page-index": "0",
    "work-day-start-hour": "8",
    "work-day-start-minute": "0",
    "work-day-end-hour": "17",
    "work-day-end-minute": "0",
    "work-week-start": "1",
    "task-work-default-unit": "1",
    "task-note-default-text": "",
    "new-task-duration": "86400000",
    "new-task-work": "28800000",
    "new-task-start": "now",
    "new-resource-units": "1",
    "project-start": str(day(PROJECT_START)),
    "complete-tasks-must-be-assigned": "true",
    "scheduling-header-enabled": "false",
    "show-all-subtasks": "false",
    "priority-high-threshold": "500",
    "priority-low-threshold": "100",
    "baseline-strategy": "0",
    "baseline": "0",
    "schedule-from": "project-start",
    "automatic-scheduling": "true",
    "zero-slack-margin": "0",
    "near-to-free-slack-margin": "5",
    "low-complete-ratio": "0.25",
    "high-complete-ratio": "0.75",
    "negative-float-color": "#ff0000",
    "near-free-float-color": "#ffff00",
    "positive-float-color": "#ffffff",
    "low-complete-ratio-color": "#ff0000",
    "high-complete-ratio-color": "#00ff00",
    "critical-color": "#ff0000",
    "deadline-format": "%x %X",
    "deadline-format-language": "C",
    "deadline-format-locale": "",
    "first-weekday": "monday",
    "first-yearday": "2026-01-01",
    "weekday-monday": "1",
    "weekday-tuesday": "2",
    "weekday-wednesday": "3",
    "weekday-thursday": "4",
    "weekday-friday": "5",
    "weekday-saturday": "6",
    "weekday-sunday": "7",
    "week-mask": "1111111",
    "year-mask": "111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111",
}

PROJECT_INFO = [
    ("ProjectName", PROJECT_NAME, "string"),
    ("Organization", PROJECT_ORG, "string"),
    ("ProjectURL", "", "string"),
    ("NotificationEmails", "", "string"),
    ("Description", PROJECT_DESCRIPTION, "string"),
    ("Priority", "500", "double"),
    ("Start", str(day(PROJECT_START)), "sdate"),
    ("Finish", str(day(PROJECT_FINISH)), "sdate"),
]


def main(out_path: str):
    if os.path.exists(out_path):
        os.remove(out_path)
    con = sqlite3.connect(out_path)
    con.executescript(SCHEMA)

    con.executemany("INSERT INTO info VALUES (?, ?)", INFO_VALUES.items())
    con.executemany(
        "INSERT INTO project_info (name, value, type) VALUES (?, ?, ?)",
        PROJECT_INFO,
    )

    con.execute(
        "INSERT INTO groups (id, name, show) VALUES (1, 'Team', 1)"
    )
    con.execute(
        "INSERT INTO resources (id, name, short_name, rate, overtime_rate, units, group_id, type, priority)"
        " VALUES (1, 'Разработчик', 'Dev', 0, 0, 1, 1, 0, 0)"
    )

    con.execute(
        "INSERT INTO calendars (id, name, week_mask, year_mask, valid_from, valid_to,"
        " prev_day_mask, next_day_mask, slots_per_day)"
        " VALUES (1, 'Стандартный', 126, -1, ?, ?, '', '', 1)",
        (day(dt.date(2026, 1, 1)), -1),
    )
    con.executemany(
        "INSERT INTO calendar_exceptions (VACATION_TYPE, NAME, start_time, end_time, calendar_id)"
        " VALUES (0, ?, ?, ?, 1)",
        [("Праздник", t, t + MS_PER_DAY) for t in WORK_DAYS],
    )

    by_id = {t[0]: t for t in TASKS}
    children = {}
    for t in TASKS:
        if t[1] is not None:
            children.setdefault(t[1], []).append(t[0])

    for tid, parent, name, s, f, pct, _type in TASKS:
        start = dt.date.fromisoformat(s)
        finish = dt.date.fromisoformat(f)
        duration = int((finish - start).days) * MS_PER_DAY
        work = int(duration * 0.3333)  # 8 ч из 24 ч суток
        is_summary = tid in children
        con.execute(
            "INSERT INTO tasks (id, name, type, duration, complete_ratio, start, finish,"
            " parent_id, notes, priority, scheduled_start, scheduled_finish, is_milestone,"
            " status, cost, work, is_delayed, is_fixed_start, is_critical, is_summary, has_child)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tid, name, 0, duration, pct / 100.0,
                day(start), day(finish), parent, None, 1,
                day(start), day(finish), 0, 0, 0, work,
                0, 0, 0, 1 if is_summary else 0, 1 if is_summary else 0,
            ),
        )
        if not is_summary:
            con.execute(
                "INSERT INTO assignments (task_id, resource_id, units, work, cost)"
                " VALUES (?, 1, 1, ?, 0)",
                (tid, work),
            )

    # DEPENDS задаётся как (последователь, предшественник) finish->start
    for succ, pred in DEPENDS:
        con.execute(
            "INSERT INTO task_deps (task_id, dep_id, type, lag, require_full)"
            " VALUES (?, ?, 2, 0, 1)",
            (succ, pred),
        )
        con.execute(
            "INSERT INTO links (predecessor_id, successor_id, comment, type, lag)"
            " VALUES (?, ?, '', 2, 0)",
            (pred, succ),
        )

    con.commit()

    # Самопроверка целостности данных перед записью готового файла
    cur = con.cursor()
    errors = []
    byid = {r[0]: r for r in cur.execute(
        "SELECT id, parent_id, start, finish FROM tasks")}
    for tid, (_p, parent, s, f) in byid.items():
        if parent is not None:
            ps, pf = byid[parent][2], byid[parent][3]
            if s < ps or f > pf:
                errors.append(f"задача {tid} вне окна родителя {parent}")
    for p, s in cur.execute("SELECT predecessor_id, successor_id FROM links"):
        if byid[p][3] > byid[s][2]:
            errors.append(f"связь FS {p}->{s}: конец предшественника позже начала")
    if errors:
        con.close()
        raise SystemExit("ОШИБКИ в данных:\n" + "\n".join(errors))
    con.close()
    print(f"OK: создан {out_path} ({len(TASKS)} задач, {os.path.getsize(out_path)} байт)")


if __name__ == "__main__":
    main(os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects.planner"))
