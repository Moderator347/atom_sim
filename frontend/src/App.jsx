import { useState, useEffect, useMemo, useRef } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls, Sphere, Cylinder, Text } from '@react-three/drei'
import axios from 'axios'
import * as THREE from 'three'
import { 
  Box, Typography, Slider, Select, MenuItem, FormControl, 
  InputLabel, Paper, CircularProgress, Alert, Switch, 
  FormControlLabel, Divider, TextField
} from '@mui/material'

const ELEMENT_COLORS = {
  'Cu': '#B87333', 'Al': '#AAAAAA', 'Fe': '#8B4513',
  'C': '#333333', 'Si': '#696969', 'Au': '#FFD700', 'Ag': '#C0C0C0'
}

// Компонент атома
function Atom({ position, color, clipPlanes }) {
  return (
    <group position={position}>
      <Sphere args={[0.35, 16, 16]}>
        <meshStandardMaterial 
          color={color} 
          metalness={0.6} 
          roughness={0.3}
          clippingPlanes={clipPlanes}
          clipShadows={true}
        />
      </Sphere>
    </group>
  )
}

// Компонент связи (цилиндр между двумя атомами)
function Bond({ atom1, atom2, clipPlanes, bondColor }) {
  const start = new THREE.Vector3(atom1.x, atom1.y, atom1.z)
  const end = new THREE.Vector3(atom2.x, atom2.y, atom2.z)
  
  // Вычисляем длину и направление
  const distance = start.distanceTo(end)
  const direction = new THREE.Vector3().subVectors(end, start)
  const midpoint = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
  
  // Создаем цилиндр
  const cylinderRef = useRef()
  
  // Кватернион для ориентации цилиндра
  const quaternion = useMemo(() => {
    const axis = new THREE.Vector3(0, 1, 0)
    const q = new THREE.Quaternion()
    q.setFromUnitVectors(axis, direction.clone().normalize())
    return q
  }, [direction])

  return (
    <group position={midpoint} quaternion={quaternion}>
      <Cylinder 
        args={[0.08, 0.08, distance, 8]} 
        rotation={[Math.PI / 2, 0, 0]}
      >
        <meshStandardMaterial 
          color={bondColor} 
          transparent 
          opacity={0.7}
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

function AtomScene({ atoms, bonds, clipEnabled, clipAxis, clipPosition, showBonds, bondColor }) {
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
      {/* Атомы */}
      {atoms.map((atom, index) => (
        <Atom 
          key={`atom-${index}`} 
          position={[atom.x, atom.y, atom.z]} 
          color={ELEMENT_COLORS[atom.type] || '#ffffff'}
          clipPlanes={clippingPlanes}
        />
      ))}
      
      {/* Связи */}
      {showBonds && bonds.map((bond, index) => (
        <Bond 
          key={`bond-${index}`}
          atom1={atoms[bond.atom1]}
          atom2={atoms[bond.atom2]}
          clipPlanes={clippingPlanes}
          bondColor={bondColor}
        />
      ))}
      
      {/* Плоскость среза */}
      {clipEnabled && (
        <ClippingPlane axis={clipAxis} position={clipPosition} />
      )}
      
      <ambientLight intensity={0.6} />
      <pointLight position={[20, 20, 20]} intensity={1.5} />
      <pointLight position={[-20, -20, -20]} intensity={0.5} />
      <OrbitControls makeDefault />
    </>
  )
}

function App() {
  const [atoms, setAtoms] = useState([])
  const [bonds, setBonds] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({ count: 0, bondCount: 0, lattice: '' })
  
  // Параметры структуры
  const [element, setElement] = useState('Cu')
  const [size, setSize] = useState(4)
  const [lattice, setLattice] = useState('fcc')
  
  // Параметры среза
  const [clipEnabled, setClipEnabled] = useState(true)
  const [clipAxis, setClipAxis] = useState('x')
  const [clipPosition, setClipPosition] = useState(0)
  const [maxClipRange, setMaxClipRange] = useState(15)
  
  // Параметры связей
  const [showBonds, setShowBonds] = useState(true)
  const [bondColor, setBondColor] = useState('#666666')

  // Загрузка данных
  const fetchAtoms = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await axios.get('http://localhost:8000/api/atoms', {
        params: { element, size, lattice, show_bonds: showBonds }
      })
      setAtoms(response.data.atoms)
      setBonds(response.data.bonds)
      setStats({ 
        count: response.data.total_count, 
        bondCount: response.data.bond_count,
        lattice: response.data.lattice_type 
      })
      
      if (response.data.atoms.length > 0) {
        const coords = response.data.atoms.map(a => [a.x, a.y, a.z]).flat()
        const minCoord = Math.min(...coords)
        const maxCoord = Math.max(...coords)
        setMaxClipRange(Math.max(Math.abs(minCoord), Math.abs(maxCoord)) + 5)
        setClipPosition((minCoord + maxCoord) / 2)
      }
    } catch (err) {
      setError('Не удалось загрузить данные от сервера')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchAtoms()
    }, 500)
    return () => clearTimeout(timer)
  }, [element, size, lattice, showBonds])

  return (
    <Box sx={{ display: 'flex', height: '100vh', width: '100vw' }}>
      {/* Панель управления */}
      <Paper 
        elevation={3} 
        sx={{ 
          width: 340, 
          p: 3, 
          m: 2, 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 2,
          zIndex: 10,
          overflowY: 'auto'
        }}
      >
        <Typography variant="h5" fontWeight="bold">⚛️ Настройки</Typography>
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
            <Select value={bondColor} label="Цвет связей" onChange={(e) => setBondColor(e.target.value)} fullWidth size="small">
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
            <Typography variant="body2">Атомов: <b>{stats.count}</b></Typography>
            <Typography variant="body2">Связей: <b>{stats.bondCount}</b></Typography>
            <Typography variant="body2">Структура: <b>{stats.lattice}</b></Typography>
            {stats.count > 0 && stats.bondCount > 0 && (
              <Typography variant="body2" sx={{ fontSize: '0.75rem', color: '#666' }}>
                Ср. связей на атом: {(stats.bondCount * 2 / stats.count).toFixed(2)}
              </Typography>
            )}
          </Paper>
        </Box>
      </Paper>

      {/* 3D Сцена */}
      <Box sx={{ flexGrow: 1, position: 'relative' }}>
        {loading && (
          <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 5 }}>
            <CircularProgress size={60} />
          </Box>
        )}
        <Canvas camera={{ position: [15, 15, 15], fov: 50 }} gl={{ localClippingEnabled: true }}>
          <AtomScene 
            atoms={atoms} 
            bonds={bonds}
            clipEnabled={clipEnabled}
            clipAxis={clipAxis}
            clipPosition={clipPosition}
            showBonds={showBonds}
            bondColor={bondColor}
          />
        </Canvas>
      </Box>
    </Box>
  )
}

export default App
