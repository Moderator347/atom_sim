from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from collections import Counter
from ase import Atoms
from ase.build import bulk
import numpy as np
from scipy.spatial import cKDTree

try:
    import model as nn_model
    NN_AVAILABLE = True
except Exception:  # torch не установлен — работаем на геометрическом алгоритме
    nn_model = None
    NN_AVAILABLE = False

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Atom(BaseModel):
    x: float
    y: float
    z: float
    type: str
    index: int

class Bond(BaseModel):
    atom1: int  # Индекс первого атома
    atom2: int  # Индекс второго атома
    distance: float
    probability: Optional[float] = None  # вероятность связи от нейросети

class AtomGrid(BaseModel):
    atoms: List[Atom]
    bonds: List[Bond]
    total_count: int
    bond_count: int
    lattice_type: str


class PredictRequest(BaseModel):
    """Запрос на предсказание связей нейросетью для произвольного набора атомов."""
    atoms: List[Atom]
    use_nn: bool = True  # False — геометрический алгоритм (baseline)


class PredictResponse(BaseModel):
    bonds: List[Bond]
    bond_count: int
    engine: str  # 'neural_network' | 'geometry'


class ReactionFrame(BaseModel):
    """Кадр временной шкалы симуляции."""
    t: float                      # время, пс
    atoms: List[Atom]             # позиции атомов в этот момент
    bonds: List[Bond]
    molecules: List[dict]         # «вещества» — связные компоненты графа связей


class ReactionRequest(BaseModel):
    host_element: str = "Cu"      # основной материал решётки
    size: int = 3
    lattice: str = "fcc"
    intruder_symbol: str = "O"    # атом другого вещества
    intruder_positions: List[List[float]] = [[0.0, 0.0, 0.0]]  # куда поместить
    duration_ps: float = 10.0     # длительность симуляции
    steps: int = 60               # число кадров временной шкалы
    temperature_K: float = 300.0  # температура (влияет на амплитуду тепловых колебаний)


class ReactionResponse(BaseModel):
    frames: List[ReactionFrame]
    final_molecules: List[dict]
    engine: str

# Радиусы атомов для определения связей (в ангстремах)
ATOMIC_RADII = {
    'H': 0.31, 'C': 0.76, 'N': 0.71, 'O': 0.66,
    'F': 0.57, 'Si': 1.11, 'P': 1.07, 'S': 1.05,
    'Cu': 1.32, 'Al': 1.21, 'Fe': 1.26, 'Au': 1.44,
    'Ag': 1.45, 'Zn': 1.33, 'Ni': 1.24, 'Co': 1.25
}

def calculate_bonds(atoms_data, bond_threshold_factor=1.2):
    """Вычисляет связи между атомами на основе расстояний"""
    if len(atoms_data) == 0:
        return []
    
    # Создаём массив координат
    positions = np.array([[a['x'], a['y'], a['z']] for a in atoms_data])
    symbols = [a['type'] for a in atoms_data]
    
    # Используем KD-дерево для быстрого поиска соседей
    tree = cKDTree(positions)
    
    bonds = []
    
    # Максимальный радиус поиска: не меньше максимального порога связи
    # (сумма двух самых больших атомных радиусов * коэффициент),
    # иначе связи между крупными атомами (Cu, Au, Ag...) будут потеряны.
    max_radius = max(ATOMIC_RADII.values())
    max_search_radius = 2 * max_radius * bond_threshold_factor
    
    # query_pairs находит все уникальные пары атомов (i < j) в заданном радиусе за один проход
    for i, j in tree.query_pairs(max_search_radius):
        radius_i = ATOMIC_RADII.get(symbols[i], 1.0)
        radius_j = ATOMIC_RADII.get(symbols[j], 1.0)
        
        # Вычисляем расстояние
        distance = np.linalg.norm(positions[i] - positions[j])
        
        # Порог для связи (сумма радиусов * коэффициент)
        bond_threshold = (radius_i + radius_j) * bond_threshold_factor
        
        if distance <= bond_threshold:
            bonds.append({
                "atom1": int(i),
                "atom2": int(j),
                "distance": round(float(distance), 3)
            })
    
    return bonds


def find_candidate_pairs(atoms_data, bond_threshold_factor=1.2):
    """Возвращает все пары атомов, потенциально способные образовать связь."""
    if len(atoms_data) == 0:
        return []
    positions = np.array([[a['x'], a['y'], a['z']] for a in atoms_data])
    tree = cKDTree(positions)
    max_radius = max(ATOMIC_RADII.values())
    return list(tree.query_pairs(2 * max_radius * bond_threshold_factor))


def detect_molecules(atoms_data, bonds):
    """Находит «вещества» — связные компоненты графа связей.

    Возвращает список молекул/кластеров с формулой (например Cu4O)."""
    n = len(atoms_data)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for b in bonds:
        union(b['atom1'] if isinstance(b, dict) else b.atom1,
              b['atom2'] if isinstance(b, dict) else b.atom2)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    molecules = []
    for members in groups.values():
        counts = Counter(atoms_data[i]['type'] for i in members)
        formula = ''.join(f"{el}{cnt if cnt > 1 else ''}" for el, cnt in sorted(counts.items()))
        molecules.append({
            "formula": formula,
            "size": len(members),
            "composition": dict(counts),
            "atom_indices": sorted(members),
        })
    molecules.sort(key=lambda m: (-m['size'], m['formula']))
    return molecules


@app.post("/api/predict_bonds", response_model=PredictResponse)
def predict_bonds_endpoint(req: PredictRequest):
    """Предсказание связей натренированной нейросетью для произвольного набора атомов.

    Используется, например, когда в решётку одного вещества помещают атомы другого:
    модель по парным признакам (радиусы, электроотрицательности, расстояние)
    выдаёт вероятность образования связи для каждой пары-кандидата."""
    atoms_data = [a.model_dump() for a in req.atoms]
    if len(atoms_data) < 2:
        return {"bonds": [], "bond_count": 0, "engine": "geometry"}

    candidates = find_candidate_pairs(atoms_data)
    positions = np.array([[a['x'], a['y'], a['z']] for a in atoms_data])

    if req.use_nn and NN_AVAILABLE:
        bonds = nn_model.predict_bonds(atoms_data, positions, candidates)
        engine = "neural_network"
    else:
        bonds = calculate_bonds(atoms_data)
        engine = "geometry"

    return {"bonds": bonds, "bond_count": len(bonds), "engine": engine}


@app.post("/api/train_model")
def train_model_endpoint(epochs: int = Query(default=8, ge=1, le=50)):
    """Явная перетренировка нейросетевой модели предсказания связей."""
    if not NN_AVAILABLE:
        raise HTTPException(status_code=503, detail="PyTorch недоступен на сервере")
    acc = nn_model.train_model(epochs=epochs, verbose=False)
    nn_model._loaded_model = None  # сбросить кэш, чтобы загрузились новые веса
    return {"status": "ok", "accuracy": round(acc, 4)}


@app.get("/api/model_info")
def model_info():
    if not NN_AVAILABLE:
        return {"available": False, "reason": "torch не установлен"}
    import os
    path = nn_model.MODEL_PATH
    exists = os.path.exists(path)
    acc = None
    if exists:
        try:
            import torch
            ckpt = torch.load(path, map_location="cpu", weights_only=True)
            acc = ckpt.get("accuracy")
        except Exception:
            pass
    return {
        "available": True,
        "trained": exists,
        "architecture": "MLP ->64->64->1 (sigmoid)",
        "features": "радиус, электроотрицательность, one-hot элемента, расстояние",
        "accuracy": round(acc, 4) if acc is not None else None,
    }


@app.post("/api/reaction", response_model=ReactionResponse)
def simulate_reaction(req: ReactionRequest):
    """Упрощённая молекулярная симуляция с временной шкалой.

    Строит хозяйскую решётку, помещает в неё атомы другого вещества,
    затем на каждом шаге добавляет тепловые смещения позиций и заново
    предсказывает связи (нейросетью либо геометрически). Связные
    компоненты графа связей трактуются как получившиеся «вещества»."""
    if not (1 <= req.size <= 6):
        raise HTTPException(status_code=422, detail="Параметр size должен быть от 1 до 6")
    if not (10 <= req.steps <= 200):
        raise HTTPException(status_code=422, detail="Параметр steps должен быть от 10 до 200")

    supported = ("fcc", "bcc", "hcp", "diamond", "rock salt", "sc")
    host = req.host_element
    rng = np.random.default_rng(1234)

    # --- построение базовой структуры ---
    base_atoms = []
    if req.lattice == "sc":
        a = 2 * ATOMIC_RADII.get(host, 1.0)
        positions = [[i * a, j * a, k * a]
                     for i in range(req.size) for j in range(req.size) for k in range(req.size)]
        crystal = Atoms(symbols=[host] * len(positions), positions=positions)
    elif req.lattice in supported:
        try:
            a = float(bulk(host).cell[0][0])
        except Exception:
            a = 2 * ATOMIC_RADII.get(host, 1.0)
        a = max(a, 2 * ATOMIC_RADII.get(host, 1.0))
        try:
            crystal = bulk(host, crystalstructure=req.lattice, a=a, cubic=True)
            crystal *= req.size
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"Не удалось построить решётку '{req.lattice}' для '{host}': {e}")
    else:
        raise HTTPException(status_code=400,
                            detail=f"Неподдерживаемый тип решётки: '{req.lattice}'")

    for pos in crystal.positions:
        base_atoms.append({"x": float(pos[0]), "y": float(pos[1]),
                           "z": float(pos[2]), "type": host})

    # центрируем относительно геометрического центра — удобно для фронтенда
    center = np.mean([[a['x'], a['y'], a['z']] for a in base_atoms], axis=0)
    for atom in base_atoms:
        atom['x'] -= center[0]; atom['y'] -= center[1]; atom['z'] -= center[2]

    # вставляем «чужие» атомы (по умолчанию — в центр куба)
    for p in req.intruder_positions:
        if len(p) != 3:
            raise HTTPException(status_code=422, detail="Каждая позиция intruder — [x, y, z]")
        base_atoms.append({"x": float(p[0]), "y": float(p[1]),
                           "z": float(p[2]), "type": req.intruder_symbol})

    for i, atom in enumerate(base_atoms):
        atom['index'] = i

    base_pos = np.array([[a['x'], a['y'], a['z']] for a in base_atoms])
    candidates = find_candidate_pairs(base_atoms)

    use_nn = NN_AVAILABLE
    engine = "neural_network" if use_nn else "geometry"

    # амплитуда теплового смещения: ~0.01 Å при 300 K; масштабируется sqrt(T/m)
    mass = {'H': 1, 'C': 12, 'N': 14, 'O': 16, 'Si': 28, 'Cu': 63.5,
            'Al': 27, 'Fe': 56, 'Au': 197, 'Ag': 108}.get(host, 50)
    amp = 0.01 * (300.0 / mass) ** 0.5 * (req.temperature_K / 300.0) ** 0.5

    frames = []
    dt = req.duration_ps / req.steps
    for step in range(req.steps + 1):
        t = step * dt
        progress = min(1.0, t / max(req.duration_ps * 0.5, 1e-6))
        noisy = base_pos + rng.normal(0, amp, base_pos.shape) * progress
        frame_atoms = [dict(a) for a in base_atoms]
        for i in range(len(frame_atoms)):
            frame_atoms[i]['x'] = float(noisy[i][0])
            frame_atoms[i]['y'] = float(noisy[i][1])
            frame_atoms[i]['z'] = float(noisy[i][2])

        if use_nn:
            bonds = nn_model.predict_bonds(frame_atoms, noisy, candidates)
        else:
            bonds = calculate_bonds(frame_atoms)

        molecules = detect_molecules(frame_atoms, bonds)
        frames.append({
            "t": round(t, 3),
            "atoms": frame_atoms,
            "bonds": bonds,
            "molecules": molecules,
        })

    return {
        "frames": frames,
        "final_molecules": frames[-1]["molecules"],
        "engine": engine,
    }

@app.get("/api/atoms", response_model=AtomGrid)
def get_atoms(
    element: str = Query(default="Cu", description="Химический элемент"),
    size: int = Query(default=5, description="Размер куба"),
    lattice: str = Query(default="fcc", description="Тип решетки"),
    show_bonds: bool = Query(default=True, description="Показывать связи")
):
    """Генерирует кристаллическую решетку с расчётом связей"""
    # Валидация параметров
    if not (1 <= size <= 10):
        raise HTTPException(status_code=422, detail="Параметр size должен быть от 1 до 10")

    supported_structures = ("fcc", "bcc", "hcp", "diamond", "rock salt", "sc")

    # Стандартные параметры решётки для элементов (Å)
    lattice_params = {
        "Cu": {"fcc": 3.615},
        "Al": {"fcc": 4.05},
        "Fe": {"bcc": 2.866, "fcc": 3.593},
        "C": {"diamond": 3.567},
        "Si": {"diamond": 5.431},
        "Au": {"fcc": 4.078},
        "Ag": {"fcc": 4.086},
    }

    if lattice == "sc":
        # ASE не поддерживает crystalstructure="sc" — строим простую кубическую решётку вручную.
        # Параметр решётки берём равным удвоенному ковалентному радиусу элемента,
        # чтобы атомы касались друг друга и связи корректно определялись.
        a = 2 * ATOMIC_RADII.get(element, 1.0)
        positions = [
            [i * a, j * a, k * a]
            for i in range(size)
            for j in range(size)
            for k in range(size)
        ]
        crystal = Atoms(symbols=[element] * len(positions), positions=positions,
                        cell=[size * a, size * a, size * a])
    elif lattice in supported_structures:
        try:
            # Стандартный параметр решётки для элемента (из справочных данных ASE),
            # если он есть; иначе — из таблицы ниже.
            try:
                default_a = float(bulk(element).cell[0][0])
            except Exception:
                default_a = None

            # Физически корректный параметр для конкретной пары элемент+структура имеет приоритет.
            # В остальных случаях берём стандартный параметр, но не меньше удвоенного
            # ковалентного радиуса атома (иначе атомы «не касаются» друг друга
            # и связи между ними не будут определены).
            a = lattice_params.get(element, {}).get(lattice)
            if a is None:
                if default_a is not None:
                    a = max(default_a, 2 * ATOMIC_RADII.get(element, 1.0))
                else:
                    a = 2 * ATOMIC_RADII.get(element, 1.0)

            crystal = bulk(element, crystalstructure=lattice, a=a, cubic=True)
            crystal *= size
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Не удалось построить решётку '{lattice}' для элемента '{element}': {e}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый тип решётки: '{lattice}'. Доступны: {', '.join(supported_structures)}",
        )

    atoms_data = []
    for i, atom in enumerate(crystal):
        atoms_data.append({
            "x": float(atom.position[0]),
            "y": float(atom.position[1]),
            "z": float(atom.position[2]),
            "type": atom.symbol,
            "index": i
        })

    # Вычисляем связи если нужно
    bonds_data = []
    if show_bonds:
        bonds_data = calculate_bonds(atoms_data)

    return {
        "atoms": atoms_data,
        "bonds": bonds_data,
        "total_count": len(atoms_data),
        "bond_count": len(bonds_data),
        "lattice_type": f"{element}-{lattice}-{size}x{size}x{size}"
    }

@app.get("/api/elements")
def get_available_elements():
    return {
        "elements": [
            {"symbol": "Cu", "name": "Copper", "color": "#B87333"},
            {"symbol": "Al", "name": "Aluminum", "color": "#AAAAAA"},
            {"symbol": "Fe", "name": "Iron", "color": "#8B4513"},
            {"symbol": "C", "name": "Carbon", "color": "#333333"},
            {"symbol": "Si", "name": "Silicon", "color": "#696969"},
            {"symbol": "Au", "name": "Gold", "color": "#FFD700"},
            {"symbol": "Ag", "name": "Silver", "color": "#C0C0C0"},
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)