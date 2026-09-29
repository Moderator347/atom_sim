import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Sphere, Cylinder } from '@react-three/drei'
import axios from 'axios'
import * as THREE from 'three'
import {
  Box, Typography, Slider, Select, MenuItem, FormControl,
  InputLabel, Paper, CircularProgress, Alert, Switch,
  FormControlLabel, Divider, Button, Chip, IconButton, Tooltip
} from '@mui/material'

const API = 'http://localhost:8000'

const ELEMENT_COLORS = {
  'Cu': '#B87333', 'Al': '#AAAAAA', 'Fe': '#8B4513',
  'C': '#333333', 'Si': '#696969', 'Au': '#FFD700', 'Ag': '#C0C0C0',
  'O': '#FF2D2D', 'N': '#3050F8', 'H': '#FFFFFF', 'S': '#FFFF30',
  'Zn': '#7D80B0', 'Ni': '#50D050', 'Co': '#F090A0', 'Ca': '#3DFF00',
}

const EXTRA_ELEMENTS = ['O', 'N', 'H', 'S', 'Zn', 'Ni', 'Co', 'Ca']

// Подсветка атома — каркасная сфера вокруг выделенного атома
function Highlight({ position, color }) {
  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[0.55, 16, 16]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.6} />
      </mesh>
    </group>
  )
}

// Компонент атома
function Atom({ position, color, clipPlanes, radius = 0.35, onClick, selected }) {
  return (
    <group position={position}>
      <Sphere
        args={[selected ? radius * 1.25 : radius, 16, 16]}
        onClick={onClick}
      >
        <meshStandardMaterial
          color={color}
          metalness={0.6}
          roughness={0.3}
          emissive={selected ? color : '#000000'}
          emissiveIntensity={selected ? 0.5 : 0}
          clippingPlanes={clipPlanes}
          clipShadows={true}
        />
      </Sphere>
    </group>
  )
}

// Компонент связи (цилиндр между двумя атомами)
function Bond({ atom1, atom2, clipPlanes, bondColor, highlighted }) {
  const start = new THREE.Vector3(atom1.x, atom1.y, atom1.z)
  const end = new THREE.Vector3(atom2.x, atom2.y, atom2.z)

  const distance = start.distanceTo(end)
  const direction = new THREE.Vector3().subVectors(end, start)
  const midpoint = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)

  const quaternion = useMemo(() => {
    const axis = new THREE.Vector3(0, 1, 0)
    const q = new THREE.Quaternion()
    q.setFromUnitVectors(axis, direction.clone().normalize())
    return q
  }, [direction])

  return (
    <group position={midpoint} quaternion={quaternion}>
      <Cylinder
        args={[highlighted ? 0.13 : 0.08, highlighted ? 0.13 : 0.08, distance, 8]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <meshStandardMaterial
          color={highlighted ? '#ff1493' : bondColor}
          transparent
          opacity={highlighted ? 0.95 : 0.7}
          emissive={highlighted ? '#ff1493' : '#000000'}
          emissiveIntensity={highlighted ? 0.6 : 0}
          clippingPlanes={clipPlanes}
          clipShadows={true}
        />
      </Cylinder>
    </group>
  )
}

// Визуализация плоскости среза
function ClippingPlane({ axis, position }) {
  const rotation = useMemo(() => {
    if (axis === 'x') return [0, Math.PI / 2, 0]
    if (axis === 'y') return [Math.PI / 2, 0, 0]
    return [0, 0, 0]
  }, [axis])

  const pos = useMemo(() => {
    if (axis === 'x') return [position, 0, 0]
    if (axis === 'y') return [0, position, 0]
    return [0, 0, position]
  }, [axis, position])

  return (
    <mesh position={pos} rotation={rotation}>
      <planeGeometry args={[30, 30]} />
      <meshBasicMaterial color="#00ff00" transparent opacity={0.15} side={THREE.DoubleSide} />
      <lineSegments>
        <edgesGeometry args={[new THREE.PlaneGeometry(30, 30)]} />
        <lineBasicMaterial color="#00ff00" linewidth={2} />
      </lineSegments>
    </mesh>
  )
}

// Невидимая сфера-ловушка кликов для режима размещения атомов
function PlacementCatcher({ enabled, onPoint }) {
  return (
    <mesh
      visible={false}
      onPointerDown={(e) => {
        if (!enabled) return
        e.stopPropagation()
        onPoint([e.point.x, e.point.y, e.point.z])
      }}
    >
      <sphereGeometry args={[60, 8, 8]} />
      <meshBasicMaterial side={THREE.BackSide} />
    </mesh>
  )
}

function AtomScene({
  atoms, bonds, clipEnabled, clipAxis, clipPosition, showBonds, bondColor,
  bgLight, highlightSet, selectedAtom, onAtomClick, placeMode, onPlacePoint,
}) {
  const clippingPlanes = useMemo(() => {
    if (!clipEnabled) return []
    const normal = new THREE.Vector3()
    if (clipAxis === 'x') normal.set(1, 0, 0)
    else if (clipAxis === 'y') normal.set(0, 1, 0)
    else normal.set(0, 0, 1)
    const plane = new THREE.Plane(normal, -clipPosition)
    return [plane]
  }, [clipEnabled, clipAxis, clipPosition])

  return (
    <>
      <color attach="background" args={[bgLight ? '#f4f6fa' : '#0d1117']} />

      {atoms.map((atom, index) => (
        <Atom
          key={`atom-${index}`}
          position={[atom.x, atom.y, atom.z]}
          color={ELEMENT_COLORS[atom.type] || '#ffffff'}
          clipPlanes={clippingPlanes}
          radius={atom.type === 'H' ? 0.22 : 0.35}
          selected={selectedAtom === index}
          onClick={(e) => { e.stopPropagation(); onAtomClick(index) }}
        />
      ))}

      {/* Выделение получившегося вещества */}
      {highlightSet && atoms.map((atom, i) =>
        highlightSet.atoms.has(i) ? (
          <Highlight key={`hl-${i}`} position={[atom.x, atom.y, atom.z]} color="#ff1493" />
        ) : null
      )}

      {showBonds && bonds.map((bond, index) => (
        <Bond
          key={`bond-${index}`}
          atom1={atoms[bond.atom1]}
          atom2={atoms[bond.atom2]}
          clipPlanes={clippingPlanes}
          bondColor={bondColor}
          highlighted={!!highlightSet && highlightSet.bonds.has(index)}
        />
      ))}

      {clipEnabled && <ClippingPlane axis={clipAxis} position={clipPosition} />}
      <PlacementCatcher enabled={placeMode} onPoint={onPlacePoint} />

      <ambientLight intensity={bgLight ? 0.9 : 0.6} />
      <pointLight position={[20, 20, 20]} intensity={1.5} />
      <pointLight position={[-20, -20, -20]} intensity={0.5} />
      <OrbitControls makeDefault enabled={!placeMode} />
    </>
  )
}

function App() {
  const [atoms, setAtoms] = useState([])
  const [bonds, setBonds] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({ count: 0, bondCount: 0, lattice: '' })
  const [engine, setEngine] = useState('geometry')

  // Параметры структуры
  const [element, setElement] = useState('Cu')
  const [size, setSize] = useState(4)
  const [lattice, setLattice] = useState('fcc')

  // Параметры среза
  const [clipEnabled, setClipEnabled] = useState(true)
  const [clipAxis, setClipAxis] = useState('x')
  const [clipPosition, setClipPosition] = useState(0)
  const [maxClipRange, setMaxClipRange] = useState(15)

  // Внешний вид
  const [showBonds, setShowBonds] = useState(true)
  const [bondColor, setBondColor] = useState('#666666')
  const [bgLight, setBgLight] = useState(false)

  // Нейросеть и добавление атомов
  const [useNN, setUseNN] = useState(true)
  const [modelInfo, setModelInfo] = useState(null)
  const [extraAtoms, setExtraAtoms] = useState([])
  const [addedElement, setAddedElement] = useState('O')
  const [placeMode, setPlaceMode] = useState(false)
  const [selectedAtom, setSelectedAtom] = useState(null)
  const [molecules, setMolecules] = useState(null)
  const [highlightFormula, setHighlightFormula] = useState(null)

  // Симуляция реакции / временная шкала
  const [frames, setFrames] = useState(null)
  const [frameIdx, setFrameIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [simLoading, setSimLoading] = useState(false)
  const playRef = useRef(null)

  // --- загрузка решётки + предсказание связей нейросетью ---
  const fetchAtoms = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await axios.get(`${API}/api/atoms`, {
        params: { element, size, lattice, show_bonds: false }
      })
      // центрируем решётку относительно её геометрического центра
      const xs = response.data.atoms.map(a => a.x)
      const ys = response.data.atoms.map(a => a.y)
      const zs = response.data.atoms.map(a => a.z)
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2
      const cz = (Math.min(...zs) + Math.max(...zs)) / 2
      const centered = response.data.atoms.map(a => ({
        ...a, x: a.x - cx, y: a.y - cy, z: a.z - cz
      }))
      setExtraAtoms([])
      setMolecules(null)
      setSelectedAtom(null)
      setHighlightFormula(null)
      setFrames(null)
      setPlaying(false)
      setMaxClipRange(Math.max(...centered.flatMap(a => [Math.abs(a.x), Math.abs(a.y), Math.abs(a.z)])) + 3)
      setClipPosition(0)

      const pred = await axios.post(`${API}/api/predict_bonds`, { atoms: centered, use_nn: useNN })
      setAtoms(centered)
      setBonds(pred.data.bonds)
      setEngine(pred.data.engine)
      setStats({
        count: centered.length,
        bondCount: pred.data.bonds.length,
        lattice: response.data.lattice_type
      })
    } catch (err) {
      setError('Не удалось получить данные от сервера. Проверьте, что backend запущен на порту 8000.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [element, size, lattice, useNN])

  useEffect(() => {
    const timer = setTimeout(fetchAtoms, 500)
    return () => clearTimeout(timer)
  }, [fetchAtoms])

  // информация о модели
  useEffect(() => {
    axios.get(`${API}/api/model_info`)
      .then(r => setModelInfo(r.data))
      .catch(() => setModelInfo(null))
  }, [])

  // --- пересчёт связей при изменении набора атомов ---
  const recomputeBonds = async (allAtoms) => {
    if (allAtoms.length < 2) return
    try {
      const pred = await axios.post(`${API}/api/predict_bonds`, { atoms: allAtoms, use_nn: useNN })
      setBonds(pred.data.bonds)
      setEngine(pred.data.engine)
      setStats(s => ({ ...s, count: allAtoms.length, bondCount: pred.data.bonds.length }))
    } catch (err) {
      setError('Ошибка предсказания связей')
      console.error(err)
    }
  }

  // добавление атома в заданную точку
  const addAtomAt = async (pos, sym) => {
    const newAtom = { x: pos[0], y: pos[1], z: pos[2], type: sym, index: 0 }
    const all = [...atoms, ...extraAtoms, newAtom].map((a, i) => ({ ...a, index: i }))
    setExtraAtoms(prev => [...prev, newAtom])
    setPlaceMode(false)
    setSelectedAtom(all.length - 1)
    await recomputeBonds(all)
  }

  const addAtomCenter = () => addAtomAt([0, 0, 0], addedElement)

  const removeSelected = async () => {
    if (selectedAtom === null) return
    let keepBase = atoms
    let keepExtra = extraAtoms
    if (selectedAtom < atoms.length) {
      keepBase = atoms.filter((_, i) => i !== selectedAtom)
    } else {
      const extraIdx = selectedAtom - atoms.length
      keepExtra = extraAtoms.filter((_, i) => i !== extraIdx)
    }
    const all = [...keepBase, ...keepExtra].map((a, i) => ({ ...a, index: i }))
    setAtoms(keepBase)
    setExtraAtoms(keepExtra)
    setSelectedAtom(null)
    setMolecules(null)
    setHighlightFormula(null)
    await recomputeBonds(all)
  }

  // --- анализ: какие вещества получились (связные компоненты графа связей) ---
  const analyzeSubstances = () => {
    const all = [...atoms, ...extraAtoms]
    const n = all.length
    const parent = Array.from({ length: n }, (_, i) => i)
    const find = (i) => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i] } return i }
    const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent[rb] = ra }
    bonds.forEach(b => union(b.atom1, b.atom2))
    const groups = {}
    for (let i = 0; i < n; i++) {
      const r = find(i)
      ;(groups[r] = groups[r] || []).push(i)
    }
    const mols = Object.values(groups).map(members => {
      const counts = {}
      members.forEach(i => { counts[all[i].type] = (counts[all[i].type] || 0) + 1 })
      const formula = Object.entries(counts).sort().map(([el, c]) => el + (c > 1 ? c : '')).join('')
      return { formula, size: members.length, atom_indices: members.sort((a, b) => a - b) }
    }).sort((a, b) => b.size - a.size)
    setMolecules(mols.slice(0, 30))
    setHighlightFormula(null)
  }

  // подсветка выбранного вещества
  const highlightSet = useMemo(() => {
    if (!highlightFormula || !molecules) return null
    const mol = molecules.find(m => m.formula === highlightFormula)
    if (!mol) return null
    const atomSet = new Set(mol.atom_indices)
    const bondSet = new Set()
    bonds.forEach((b, i) => {
      if (atomSet.has(b.atom1) && atomSet.has(b.atom2)) bondSet.add(i)
    })
    return { atoms: atomSet, bonds: bondSet }
  }, [highlightFormula, molecules, bonds])

  // --- симуляция реакции с временной шкалой ---
  const runReaction = async () => {
    setSimLoading(true)
    setError(null)
    try {
      const intruders = [...atoms, ...extraAtoms]
        .filter(a => a.type !== element)
        .map(a => [a.x, a.y, a.z])
      const resp = await axios.post(`${API}/api/reaction`, {
        host_element: element,
        size: Math.min(size, 5),
        lattice,
        intruder_symbol: addedElement,
        intruder_positions: intruders.length ? intruders : [[0, 0, 0]],
        duration_ps: 10,
        steps: 60,
        temperature_K: 500,
      })
      setFrames(resp.data.frames)
      setFrameIdx(resp.data.frames.length - 1)
      setEngine(resp.data.engine)
      setPlaying(true)
    } catch (e) {
      setError('Симуляция не удалась: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSimLoading(false)
    }
  }

  // проигрывание временной шкалы
  useEffect(() => {
    if (playing && frames) {
      playRef.current = setInterval(() => {
        setFrameIdx(i => {
          if (i >= frames.length - 1) { setPlaying(false); return i }
          return i + 1
        })
      }, 120)
      return () => clearInterval(playRef.current)
    }
  }, [playing, frames])

  // отображаемые данные: кадры симуляции или текущая структура
  const viewAtoms = frames ? frames[frameIdx].atoms : [...atoms, ...extraAtoms]
  const viewBonds = frames ? frames[frameIdx].bonds : bonds
  const frameMolecules = frames ? frames[frameIdx].molecules : null

  return (
    <Box sx={{ display: 'flex', height: '100vh', width: '100vw' }}>
      {/* Панель управления */}
      <Paper
        elevation={3}
        sx={{ width: 360, p: 3, m: 2, display: 'flex', flexDirection: 'column', gap: 2, zIndex: 10, overflowY: 'auto' }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h5" fontWeight="bold">⚛️ Настройки</Typography>
          <Tooltip title={bgLight ? 'Переключить на тёмный фон' : 'Переключить на светлый фон'}>
            <IconButton onClick={() => setBgLight(v => !v)} size="small" color="primary">
              {bgLight ? '🌙' : '☀️'}
            </IconButton>
          </Tooltip>
        </Box>
        <Divider />

        {/* Структура */}
        <Typography variant="subtitle1" fontWeight="bold">📦 Структура</Typography>

        <FormControl fullWidth size="small">
          <InputLabel>Элемент</InputLabel>
          <Select value={element} label="Элемент" onChange={(e) => setElement(e.target.value)}>
            <MenuItem value="Cu">🟠 Медь (Cu)</MenuItem>
            <MenuItem value="Al">⚪ Алюминий (Al)</MenuItem>
            <MenuItem value="Fe">🟤 Железо (Fe)</MenuItem>
            <MenuItem value="C">⚫ Углерод (C)</MenuItem>
            <MenuItem value="Si">⚫ Кремний (Si)</MenuItem>
            <MenuItem value="Au">🟡 Золото (Au)</MenuItem>
            <MenuItem value="Ag">⚪ Серебро (Ag)</MenuItem>
          </Select>
        </FormControl>

        <Box>
          <Typography gutterBottom variant="body2">Размер куба: {size}x{size}x{size}</Typography>
          <Slider value={size} onChange={(e, val) => setSize(val)} min={2} max={8} step={1} valueLabelDisplay="auto" size="small" />
        </Box>

        <FormControl fullWidth size="small">
          <InputLabel>Тип решетки</InputLabel>
          <Select value={lattice} label="Тип решетки" onChange={(e) => setLattice(e.target.value)}>
            <MenuItem value="fcc">FCC (ГЦК)</MenuItem>
            <MenuItem value="bcc">BCC (ОЦК)</MenuItem>
            <MenuItem value="sc">SC (Простая)</MenuItem>
            <MenuItem value="diamond">Diamond (Алмаз)</MenuItem>
          </Select>
        </FormControl>

        <Divider sx={{ my: 1 }} />

        {/* Добавление атомов */}
        <Typography variant="subtitle1" fontWeight="bold">➕ Добавление атомов</Typography>
        <FormControl fullWidth size="small">
          <InputLabel>Вставляемый атом</InputLabel>
          <Select value={addedElement} label="Вставляемый атом" onChange={(e) => setAddedElement(e.target.value)}>
            {EXTRA_ELEMENTS.map(s => (
              <MenuItem key={s} value={s}>
                <Box component="span" sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: ELEMENT_COLORS[s], mr: 1, display: 'inline-block', border: '1px solid #999' }} />
                {s}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" size="small" onClick={addAtomCenter} sx={{ flex: 1 }}>
            ⬤ В центр куба
          </Button>
          <Button
            variant={placeMode ? 'outlined' : 'text'}
            size="small"
            color={placeMode ? 'error' : 'primary'}
            onClick={() => setPlaceMode(v => !v)}
            sx={{ flex: 1 }}
          >
            {placeMode ? 'Кликните в сцене…' : '🎯 В любую точку (клик в 3D)'}
          </Button>
        </Box>
        {extraAtoms.length > 0 && (
          <Typography variant="caption" color="text.secondary">
            Добавлено атомов: {extraAtoms.length}. Клик по атому выделяет его.
          </Typography>
        )}
        <Button variant="outlined" size="small" color="error" disabled={selectedAtom === null} onClick={removeSelected}>
          🗑 Удалить выбранный атом
        </Button>

        <Divider sx={{ my: 1 }} />

        {/* Нейросеть */}
        <Typography variant="subtitle1" fontWeight="bold">🧠 Нейросеть предсказания связей</Typography>
        <FormControlLabel
          control={<Switch checked={useNN} onChange={(e) => setUseNN(e.target.checked)} />}
          label={useNN ? 'Предсказывать связи моделью (NN)' : 'Геометрический алгоритм'}
        />
        {modelInfo && (
          <Typography variant="caption" color="text.secondary">
            Модель: MLP • обучена: {modelInfo.trained ? 'да' : 'нет'} • accuracy: {modelInfo.accuracy ?? '—'}
            {' '}• движок сейчас: {engine === 'neural_network' ? '🧠 neural_network' : '📐 geometry'}
          </Typography>
        )}

        <Divider sx={{ my: 1 }} />

        {/* Реакция / временная шкала */}
        <Typography variant="subtitle1" fontWeight="bold">⚗️ Симуляция реакции</Typography>
        <Button variant="contained" color="secondary" onClick={runReaction} disabled={simLoading}>
          {simLoading ? 'Расчёт…' : '▶ Запустить симуляцию внедрения атома'}
        </Button>
        {frames && (
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button size="small" onClick={() => setPlaying(p => !p)}>
                {playing ? '⏸ Пауза' : '▶ Играть'}
              </Button>
              <Button size="small" onClick={() => { setFrames(null); setPlaying(false) }}>✖ Закрыть</Button>
              <Typography variant="caption">
                t = {frames[frameIdx].t.toFixed(1)} пс ({frameIdx + 1}/{frames.length})
              </Typography>
            </Box>
            <Slider
              value={frameIdx}
              onChange={(e, v) => { setPlaying(false); setFrameIdx(v) }}
              min={0} max={frames.length - 1} step={1} size="small"
              aria-label="Временная шкала"
            />
            {frameMolecules && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                {frameMolecules.slice(0, 6).map((m, i) => (
                  <Chip key={i} size="small" label={`${m.formula} (${m.size})`} variant="outlined" />
                ))}
              </Box>
            )}
          </Box>
        )}

        <Divider sx={{ my: 1 }} />

        {/* Анализ веществ */}
        <Typography variant="subtitle1" fontWeight="bold">🔬 Получившиеся вещества</Typography>
        <Button variant="outlined" size="small" onClick={analyzeSubstances}>
          Проанализировать связи → вещества
        </Button>
        {molecules && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {molecules.map((m, i) => (
              <Chip
                key={i}
                size="small"
                label={`${m.formula} · ${m.size}`}
                color={highlightFormula === m.formula ? 'secondary' : 'default'}
                onClick={() => setHighlightFormula(hf => hf === m.formula ? null : m.formula)}
              />
            ))}
          </Box>
        )}
        {highlightFormula && (
          <Typography variant="caption" color="secondary">
            Подсвечено вещество {highlightFormula} (розовые атомы и связи)
          </Typography>
        )}

        <Divider sx={{ my: 1 }} />

        {/* Срез */}
        <Typography variant="subtitle1" fontWeight="bold">🔪 Срез</Typography>
        <FormControlLabel
          control={<Switch checked={clipEnabled} onChange={(e) => setClipEnabled(e.target.checked)} />}
          label="Включить срез"
        />
        {clipEnabled && (
          <>
            <FormControl fullWidth size="small">
              <InputLabel>Ось среза</InputLabel>
              <Select value={clipAxis} label="Ось среза" onChange={(e) => setClipAxis(e.target.value)}>
                <MenuItem value="x">X (Красная)</MenuItem>
                <MenuItem value="y">Y (Зеленая)</MenuItem>
                <MenuItem value="z">Z (Синяя)</MenuItem>
              </Select>
            </FormControl>
            <Box>
              <Typography gutterBottom variant="body2">Положение: {clipPosition.toFixed(1)} Å</Typography>
              <Slider value={clipPosition} onChange={(e, val) => setClipPosition(val)} min={-maxClipRange} max={maxClipRange} step={0.5} valueLabelDisplay="auto" size="small" />
            </Box>
          </>
        )}

        <Divider sx={{ my: 1 }} />

        {/* Связи */}
        <Typography variant="subtitle1" fontWeight="bold">🔗 Связи</Typography>
        <FormControlLabel
          control={<Switch checked={showBonds} onChange={(e) => setShowBonds(e.target.checked)} />}
          label="Показывать связи"
        />
        {showBonds && (
          <Box>
            <Typography gutterBottom variant="body2">Цвет связей</Typography>
            <Select value={bondColor} onChange={(e) => setBondColor(e.target.value)} fullWidth size="small">
              <MenuItem value="#666666">⚫ Серый</MenuItem>
              <MenuItem value="#00ff00">🟢 Зелёный</MenuItem>
              <MenuItem value="#0088ff">🔵 Синий</MenuItem>
              <MenuItem value="#ff8800">🟠 Оранжевый</MenuItem>
              <MenuItem value="#ff0000">🔴 Красный</MenuItem>
            </Select>
          </Box>
        )}

        <Divider sx={{ my: 1 }} />

        {/* Статистика */}
        <Box sx={{ mt: 'auto' }}>
          {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
          <Paper variant="outlined" sx={{ p: 2, bgcolor: '#f5f5f5' }}>
            <Typography variant="body2">📊 Статистика:</Typography>
            <Typography variant="body2">Атомов: <b>{viewAtoms.length}</b></Typography>
            <Typography variant="body2">Связей: <b>{viewBonds.length}</b></Typography>
            <Typography variant="body2">Структура: <b>{stats.lattice}</b></Typography>
            {viewAtoms.length > 0 && viewBonds.length > 0 && (
              <Typography variant="body2" sx={{ fontSize: '0.75rem', color: '#666' }}>
                Ср. связей на атом: {(viewBonds.length * 2 / viewAtoms.length).toFixed(2)}
              </Typography>
            )}
          </Paper>
        </Box>
      </Paper>

      {/* 3D Сцена */}
      <Box sx={{ flexGrow: 1, position: 'relative', cursor: placeMode ? 'crosshair' : 'default' }}>
        {(loading || simLoading) && (
          <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 5 }}>
            <CircularProgress size={60} />
          </Box>
        )}
        <Canvas camera={{ position: [15, 15, 15], fov: 50 }} gl={{ localClippingEnabled: true }}>
          <AtomScene
            atoms={viewAtoms}
            bonds={viewBonds}
            clipEnabled={clipEnabled}
            clipAxis={clipAxis}
            clipPosition={clipPosition}
            showBonds={showBonds}
            bondColor={bondColor}
            bgLight={bgLight}
            highlightSet={frames ? null : highlightSet}
            selectedAtom={selectedAtom}
            onAtomClick={(i) => setSelectedAtom(s => s === i ? null : i)}
            placeMode={placeMode}
            onPlacePoint={(p) => addAtomAt(p, addedElement)}
          />
        </Canvas>
        {placeMode && (
          <Paper sx={{ position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)', px: 2, py: 0.5, bgcolor: 'rgba(255,20,147,0.85)', color: '#fff' }}>
            Режим размещения: кликните в 3D-сцене, чтобы добавить атом {addedElement}
          </Paper>
        )}
      </Box>
    </Box>
  )
}

export default App
