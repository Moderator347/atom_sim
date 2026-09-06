# Crystal Lattice Visualization

Веб-приложение для визуализации кристаллических решёток различных химических элементов в 3D.

## Структура проекта

```
├── backend/          # Backend на FastAPI (Python)
│   ├── main.py       # Основной файл приложения
│   └── requirements.txt
└── frontend/         # Frontend на React + Vite
    ├── src/          # Исходный код React-приложения
    ├── public/       # Статические файлы
    └── package.json
```

## Возможности

- Генерация кристаллических решёток (FCC, BCC, HCP и др.)
- Выбор химических элементов (Cu, Al, Fe, C, Si, Au, Ag)
- 3D-визуализация атомной структуры
- Расчёт и отображение связей между атомами
- Настройка размера кристаллической решётки

## Технологии

### Backend
- **FastAPI** — современный веб-фреймворк на Python
- **ASE (Atomic Simulation Environment)** — библиотека для работы с атомными структурами
- **NumPy & SciPy** — вычисления и поиск соседей через KD-дерево
- **Pydantic** — валидация данных

### Frontend
- **React 19** — UI-библиотека
- **Vite** — сборщик проектов
- **Three.js / React Three Fiber** — 3D-графика в браузере
- **Material UI** — компоненты интерфейса
- **Axios** — HTTP-запросы к API

## Установка и запуск

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Сервер запустится на `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Приложение откроется на `http://localhost:5173` (или другой порт, указанный в терминале)

## API Endpoints

- `GET /api/atoms` — получение данных об атомах и связях
  - Параметры: `element`, `size`, `lattice`, `show_bonds`
  
- `GET /api/elements` — список доступных химических элементов

## Пример запроса

```
GET /api/atoms?element=Cu&size=5&lattice=fcc&show_bonds=true
```

## Лицензия

MIT
