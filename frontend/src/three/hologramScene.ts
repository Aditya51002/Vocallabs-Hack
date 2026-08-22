import * as THREE from "three";

export interface HologramSceneHandle {
  dispose: () => void;
  pause: () => void;
  resume: () => void;
}

export interface HologramOptions {
  reducedMotion: boolean;
}

export function createHologramScene(
  container: HTMLDivElement,
  options: { reducedMotion: boolean }
): HologramSceneHandle {
  const { reducedMotion } = options;

  let width = container.clientWidth || window.innerWidth;
  let height = container.clientHeight || window.innerHeight;

  // 1. Scene, Camera, Renderer
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
  camera.position.z = 7.5;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);

  // Arrays to track all created Three.js disposable objects
  const geometries: THREE.BufferGeometry[] = [];
  const materials: THREE.Material[] = [];

  const registerGeo = <T extends THREE.BufferGeometry>(g: T): T => {
    geometries.push(g);
    return g;
  };
  const registerMat = <T extends THREE.Material>(m: T): T => {
    materials.push(m);
    return m;
  };

  // Group to hold all rotating elements
  const swarmGroup = new THREE.Group();
  scene.add(swarmGroup);

  // Colors
  const AMBER_COLOR = 0xf2b84b;
  const AMBER_DIM = 0x8a6a2c;
  const VERDIGRIS = 0x7fa98f;

  // 2. Core Particle Sphere (Fibonacci sphere distribution)
  const particleCount = reducedMotion ? 250 : 600;
  const positions = new Float32Array(particleCount * 3);
  const colors = new Float32Array(particleCount * 3);
  const baseRadius = 1.8;

  const amberC = new THREE.Color(AMBER_COLOR);
  const dimC = new THREE.Color(AMBER_DIM);
  const verdigrisC = new THREE.Color(VERDIGRIS);

  for (let i = 0; i < particleCount; i++) {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / particleCount);
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;

    const r = baseRadius * (0.92 + Math.sin(i * 1.5) * 0.12);
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta);
    const z = r * Math.cos(phi);

    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;

    // Mix amber and verdigris highlights
    const choice = Math.random();
    const c = choice > 0.85 ? verdigrisC : choice > 0.3 ? amberC : dimC;
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
  }

  const particleGeo = registerGeo(new THREE.BufferGeometry());
  particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  particleGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const particleMat = registerMat(
    new THREE.PointsMaterial({
      size: 0.045,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
    })
  );

  const particleSystem = new THREE.Points(particleGeo, particleMat);
  swarmGroup.add(particleSystem);

  // 3. Concentric Orbit Rings
  const ringGroup = new THREE.Group();
  swarmGroup.add(ringGroup);

  const ringRadii = [2.2, 2.7, 3.1];
  ringRadii.forEach((radius, idx) => {
    const segments = 96;
    const ringPositions = new Float32Array(segments * 3);
    for (let j = 0; j < segments; j++) {
      const angle = (j / segments) * Math.PI * 2;
      ringPositions[j * 3] = Math.cos(angle) * radius;
      ringPositions[j * 3 + 1] = Math.sin(angle) * radius;
      ringPositions[j * 3 + 2] = 0;
    }

    const rGeo = registerGeo(new THREE.BufferGeometry());
    rGeo.setAttribute("position", new THREE.BufferAttribute(ringPositions, 3));
    const rMat = registerMat(
      new THREE.LineBasicMaterial({
        color: idx === 1 ? VERDIGRIS : AMBER_COLOR,
        transparent: true,
        opacity: idx === 1 ? 0.25 : 0.35,
        blending: THREE.AdditiveBlending,
      })
    );
    const line = new THREE.LineLoop(rGeo, rMat);
    line.rotation.x = (idx + 1) * 0.45;
    line.rotation.y = (idx + 1) * 0.35;
    ringGroup.add(line);
  });

  // 4. Data Arc Nodes (Agent swarm nodes orbiting)
  const arcNodesGroup = new THREE.Group();
  swarmGroup.add(arcNodesGroup);

  const nodeCount = 5;
  for (let n = 0; n < nodeCount; n++) {
    const nodeGeo = registerGeo(new THREE.SphereGeometry(0.06, 12, 12));
    const nodeMat = registerMat(
      new THREE.MeshBasicMaterial({
        color: n === 3 ? VERDIGRIS : AMBER_COLOR,
        transparent: true,
        opacity: 0.9,
      })
    );
    const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
    const nAngle = (n / nodeCount) * Math.PI * 2;
    nodeMesh.position.set(Math.cos(nAngle) * 2.2, Math.sin(nAngle) * 2.2, 0);
    arcNodesGroup.add(nodeMesh);
  }

  // 5. Cursor Tracking (use local closure vars, zero React state)
  let targetRotX = 0;
  let targetRotY = 0;
  let currentRotX = 0;
  let currentRotY = 0;

  const onMouseMove = (e: MouseEvent) => {
    if (reducedMotion) return;
    const nx = (e.clientX / window.innerWidth) * 2 - 1;
    const ny = (e.clientY / window.innerHeight) * 2 - 1;
    targetRotY = nx * 0.45;
    targetRotX = -ny * 0.35;
  };
  window.addEventListener("mousemove", onMouseMove, { passive: true });

  // 6. Resize handling with ResizeObserver scoped to container
  const onResize = () => {
    if (!container) return;
    width = container.clientWidth || window.innerWidth;
    height = container.clientHeight || window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  };
  window.addEventListener("resize", onResize);

  // 7. Boot Animation Lerp
  let bootProgress = reducedMotion ? 1.0 : 0.0;
  const bootSpeed = reducedMotion ? 1.0 : 0.015;

  let animationFrameId: number | null = null;
  let isPaused = false;
  let lastTime = performance.now();

  function animate(now: number) {
    if (isPaused) return;

    const delta = (now - lastTime) / 1000;
    lastTime = now;

    // Boot expansion lerp
    if (bootProgress < 1.0) {
      bootProgress = Math.min(1.0, bootProgress + bootSpeed);
      const scale = THREE.MathUtils.lerp(0.1, 1.0, bootProgress);
      swarmGroup.scale.set(scale, scale, scale);
      particleMat.opacity = THREE.MathUtils.lerp(0.0, 0.85, bootProgress);
    }

    if (!reducedMotion) {
      // Damped cursor rotation
      currentRotX += (targetRotX - currentRotX) * 0.05;
      currentRotY += (targetRotY - currentRotY) * 0.05;

      // Base idle rotation
      swarmGroup.rotation.y += delta * 0.25;
      swarmGroup.rotation.x = currentRotX + Math.sin(now * 0.0008) * 0.08;
      swarmGroup.rotation.z = currentRotY * 0.5;

      ringGroup.rotation.z -= delta * 0.15;
      arcNodesGroup.rotation.z += delta * 0.35;
    }

    renderer.render(scene, camera);
    animationFrameId = requestAnimationFrame(animate);
  }

  animationFrameId = requestAnimationFrame(animate);

  function pause() {
    isPaused = true;
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
  }

  function resume() {
    if (isPaused) {
      isPaused = false;
      lastTime = performance.now();
      animationFrameId = requestAnimationFrame(animate);
    }
  }

  function dispose() {
    pause();

    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("resize", onResize);

    // Dispose all tracked geometries & materials
    geometries.forEach((geo) => geo.dispose());
    materials.forEach((mat) => mat.dispose());

    // Clean scene
    while (scene.children.length > 0) {
      scene.remove(scene.children[0]);
    }

    // Dispose renderer
    renderer.dispose();
    if (renderer.domElement && renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement);
    }
  }

  return { dispose, pause, resume };
}
