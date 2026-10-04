"""
Нейросетевая модель предсказания химических связей между атомами.

Архитектура: простой градиентно-обучаемый классификатор пар атомов.
Каждая пара атомов кодируется признаками:
  [r_i, r_j, Z_i, Z_j, electroneg_i, electroneg_j, dist, type-similarity]
и подаётся в 3-слойный MLP, выдающий вероятность образования связи.

Модель обучается (train) на синтетических данных, сгенерированных из
физических правил (ковалентные радиусы + порог расстояния) с шумом,
чтобы научиться предсказывать связи даже для новых комбинаций атомов,
например при «помещении атома другого вещества» в решётку.
"""

from __future__ import annotations

import os
import numpy as np
import torch
import torch.nn as nn

# Ковалентные радиусы (Å) и электроотрицательности Полинга
ELEMENT_DATA = {
    'H':  (0.31, 2.20), 'C':  (0.76, 2.55), 'N':  (0.71, 3.04),
    'O':  (0.66, 3.44), 'F':  (0.57, 3.98), 'Na': (1.66, 0.93),
    'Mg': (1.41, 1.31), 'Al': (1.21, 1.61), 'Si': (1.11, 1.90),
    'P':  (1.07, 2.19), 'S':  (1.05, 2.58), 'Cl': (1.02, 3.16),
    'K':  (2.03, 0.82), 'Ca': (1.76, 1.00), 'Ti': (1.60, 1.54),
    'Cr': (1.39, 1.66), 'Mn': (1.39, 1.55), 'Fe': (1.26, 1.83),
    'Co': (1.25, 1.88), 'Ni': (1.24, 1.91), 'Cu': (1.32, 1.90),
    'Zn': (1.33, 1.65), 'Ga': (1.22, 1.81), 'Ge': (1.20, 2.01),
    'As': (1.19, 2.18), 'Br': (1.20, 2.96), 'Ag': (1.45, 1.93),
    'Cd': (1.44, 1.69), 'In': (1.42, 1.78), 'Sn': (1.39, 1.96),
    'I':  (1.39, 2.66), 'Au': (1.44, 2.54), 'Pt': (1.36, 2.28),
    'Pb': (1.46, 2.33),
}

SYMBOLS = list(ELEMENT_DATA.keys())
SYMBOL_TO_IDX = {s: i for i, s in enumerate(SYMBOLS)}
N_ELEMENTS = len(SYMBOLS)

MAX_RADIUS = max(r for r, _ in ELEMENT_DATA.values())
MAX_EN = max(e for _, e in ELEMENT_DATA.values())


def element_features(symbol: str) -> np.ndarray:
    """Возвращает нормализованные признаки элемента [radius, electronegativity, onehot...]."""
    r, en = ELEMENT_DATA.get(symbol, (1.2, 2.0))
    onehot = np.zeros(N_ELEMENTS, dtype=np.float32)
    idx = SYMBOL_TO_IDX.get(symbol)
    if idx is not None:
        onehot[idx] = 1.0
    return np.concatenate([[r / MAX_RADIUS, en / MAX_EN], onehot]).astype(np.float32)


def pair_feature_vector(sym_i: str, sym_j: str, distance: float) -> np.ndarray:
    fi = element_features(sym_i)
    fj = element_features(sym_j)
    ri = ELEMENT_DATA.get(sym_i, (1.2, 2.0))[0]
    rj = ELEMENT_DATA.get(sym_j, (1.2, 2.0))[0]
    # расстояние относительно суммы радиусов — ключевой физический признак
    rel_dist = distance / (ri + rj)
    dEN = abs(ELEMENT_DATA.get(sym_i, (1, 2))[1] - ELEMENT_DATA.get(sym_j, (1, 2.0))[1])
    extra = np.array([distance / 5.0, rel_dist, dEN / MAX_EN], dtype=np.float32)
    return np.concatenate([fi, fj, extra]).astype(np.float32)


FEATURE_DIM = 2 * (2 + N_ELEMENTS) + 3


class BondPredictor(nn.Module):
    def __init__(self, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(FEATURE_DIM, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def generate_training_data(n_samples: int = 40000, seed: int = 42):
    """Синтетическая обучающая выборка на основе физических правил + шум."""
    rng = np.random.default_rng(seed)
    feats, labels = [], []
    for _ in range(n_samples):
        si = SYMBOLS[rng.integers(N_ELEMENTS)]
        sj = SYMBOLS[rng.integers(N_ELEMENTS)]
        ri = ELEMENT_DATA[si][0]
        rj = ELEMENT_DATA[sj][0]
        threshold = (ri + rj) * 1.2
        # половина образцов — «связанные», половина — «нет»; добавляем шум у границы
        if rng.random() < 0.5:
            dist = rng.uniform(0.5, threshold) * rng.normal(1.0, 0.05)
            label = 1.0
        else:
            dist = rng.uniform(threshold, threshold * 1.8) * rng.normal(1.0, 0.05)
            label = 0.0
        dist = float(max(dist, 0.3))
        feats.append(pair_feature_vector(si, sj, dist))
        labels.append(label)
    return np.array(feats, dtype=np.float32), np.array(labels, dtype=np.float32)


MODEL_PATH = os.path.join(os.path.dirname(__file__), "bond_model.pt")


def train_model(epochs: int = 8, n_samples: int = 40000, verbose: bool = True) -> float:
    """Обучает модель и сохраняет веса в MODEL_PATH. Возвращает финальный accuracy."""
    torch.manual_seed(0)
    X, y = generate_training_data(n_samples)
    Xt = torch.from_numpy(X)
    yt = torch.from_numpy(y)

    model = BondPredictor()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()

    ds = torch.utils.data.TensorDataset(Xt, yt)
    dl = torch.utils.data.DataLoader(ds, batch_size=512, shuffle=True)

    model.train()
    for ep in range(epochs):
        total_loss = 0.0
        for xb, yb in dl:
            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            total_loss += loss.item()
        if verbose:
            print(f"epoch {ep+1}/{epochs} loss={total_loss/len(dl):.4f}")

    model.eval()
    with torch.no_grad():
        preds = (torch.sigmoid(model(Xt)) > 0.5).float()
        acc = float((preds == yt).float().mean())
    torch.save({"state_dict": model.state_dict(), "accuracy": acc}, MODEL_PATH)
    if verbose:
        print(f"Training accuracy: {acc:.4f}. Model saved to {MODEL_PATH}")
    return acc


_loaded_model: BondPredictor | None = None


def get_model() -> BondPredictor:
    global _loaded_model
    if _loaded_model is None:
        model = BondPredictor()
        if os.path.exists(MODEL_PATH):
            ckpt = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
            model.load_state_dict(ckpt["state_dict"])
        else:
            # если модель ещё не натренирована — тренируем при первом запуске
            train_model(verbose=False)
            ckpt = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
            model.load_state_dict(ckpt["state_dict"])
        model.eval()
        _loaded_model = model
    return _loaded_model


def predict_bonds(atoms_data: list[dict], positions: np.ndarray,
                  candidate_pairs: list[tuple[int, int]],
                  prob_threshold: float = 0.5) -> list[dict]:
    """Предсказывает связи нейросетью для списка пар-кандидатов."""
    if not candidate_pairs:
        return []
    model = get_model()
    symbols = [a["type"] for a in atoms_data]
    feats = np.stack([
        pair_feature_vector(symbols[i], symbols[j],
                            float(np.linalg.norm(positions[i] - positions[j])))
        for i, j in candidate_pairs
    ])
    with torch.no_grad():
        probs = torch.sigmoid(model(torch.from_numpy(feats))).numpy()
    bonds = []
    for (i, j), p in zip(candidate_pairs, probs):
        if p >= prob_threshold:
            bonds.append({
                "atom1": int(i),
                "atom2": int(j),
                "distance": round(float(np.linalg.norm(positions[i] - positions[j])), 3),
                "probability": round(float(p), 3),
            })
    return bonds
