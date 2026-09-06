from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
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
    n_atoms = len(atoms_data)
    
    # Для каждого атома ищем соседей в радиусе
    for i in range(n_atoms):
        symbol_i = symbols[i]
        radius_i = ATOMIC_RADII.get(symbol_i, 1.0)
        
        # Максимальный радиус поиска (2 * максимальный радиус атома)
        max_search_radius = 3.0
        
        # Находим всех соседей в радиусе
        neighbors = tree.query_ball_point(positions[i], max_search_radius)
        
        for j in neighbors:
            if j <= i:  # Избегаем дублирования и связей с самим собой
                continue
            
            symbol_j = symbols[j]
            radius_j = ATOMIC_RADII.get(symbol_j, 1.0)
            
            # Вычисляем расстояние
            distance = np.linalg.norm(positions[i] - positions[j])
            
            # Порог для связи (сумма радиусов * коэффициент)
            bond_threshold = (radius_i + radius_j) * bond_threshold_factor
            
            if distance <= bond_threshold:
                bonds.append({
                    "atom1": i,
                    "atom2": j,
                    "distance": round(distance, 3)
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
    try:
        crystal = bulk(element, crystalstructure=lattice, a=3.6, cubic=True)
        crystal *= size
        
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
    except Exception as e:
        return {
            "atoms": [],
            "bonds": [],
            "total_count": 0,
            "bond_count": 0,
            "lattice_type": f"Error: {str(e)}"
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