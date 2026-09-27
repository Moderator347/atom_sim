from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from ase import Atoms
from ase.build import bulk
import numpy as np
from scipy.spatial import cKDTree

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

class AtomGrid(BaseModel):
    atoms: List[Atom]
    bonds: List[Bond]
    total_count: int
    bond_count: int
    lattice_type: str

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