import { useEffect } from 'react';

export default function useDynamicShader({ containerRef, onMouseTarget, isAnimated = true }) {
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return undefined;
    }

    let renderer;
    let scene;
    let camera;
    let mesh;
    let animationFrame;
    let resizeHandler;
    let mouseMoveHandler;
    let visibilityHandler;
    let scriptTag;

    const vertexShader = `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;

    const fragmentShader = `
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform vec2 u_mouse;
      varying vec2 vUv;

      vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
      vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
      vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

      float snoise(vec2 v) {
        const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
        vec2 i = floor(v + dot(v, C.yy));
        vec2 x0 = v - i + dot(i, C.xx);
        vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec4 x12 = x0.xyxy + C.xxzz;
        x12.xy -= i1;
        i = mod289(i);
        vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
        vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
        m *= m;
        m *= m;
        vec3 x = 2.0 * fract(p * C.www) - 1.0;
        vec3 h = abs(x) - 0.5;
        vec3 ox = floor(x + 0.5);
        vec3 a0 = x - ox;
        m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
        vec3 g;
        g.x = a0.x * x0.x + h.x * x0.y;
        g.yz = a0.yz * x12.xz + h.yz * x12.yw;
        return 130.0 * dot(m, g);
      }

      float fbm(vec2 x) {
        float v = 0.0;
        float a = 0.5;
        vec2 shift = vec2(100.0);
        mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.50));
        for (int i = 0; i < 4; ++i) {
          v += a * snoise(x);
          x = rot * x * 2.0 + shift;
          a *= 0.5;
        }
        return v;
      }

      void main() {
        vec2 uv = (vUv - 0.5) * 2.0;
        uv.x *= u_resolution.x / u_resolution.y;
        vec2 mouseOffset = (u_mouse - 0.5) * 0.3;
        vec2 waveUv = uv * 1.5 + vec2(u_time * 0.08, u_time * 0.05);

        vec2 q = vec2(0.0);
        q.x = fbm(waveUv + 0.00 * u_time);
        q.y = fbm(waveUv + vec2(1.0));

        vec2 r = vec2(0.0);
        r.x = fbm(waveUv + 1.5 * q + vec2(1.7, 9.2) + 0.12 * u_time);
        r.y = fbm(waveUv + 1.5 * q + vec2(8.3, 2.8) + 0.09 * u_time);

        float f = fbm(waveUv + r);
        float waveHeight = f * 0.4 + sin(uv.x * 2.0 + u_time * 0.3) * 0.15;
        float coverage = 1.0 - length(uv * 0.3 + mouseOffset);
        coverage = smoothstep(-0.6, 1.2, coverage + waveHeight);

        vec3 deepOcean = vec3(0.02, 0.08, 0.18);
        vec3 midOcean = vec3(0.06, 0.22, 0.42);
        vec3 shallowOcean = vec3(0.12, 0.38, 0.58);
        vec3 foam = vec3(0.85, 0.92, 0.98);
        vec3 sunlight = vec3(0.55, 0.78, 0.95);

        vec3 color = mix(deepOcean, midOcean, smoothstep(-0.2, 0.4, coverage + f * 0.3));
        color = mix(color, shallowOcean, smoothstep(0.2, 0.7, coverage + f * 0.25));
        float foamMask = smoothstep(0.6, 0.9, f + coverage * 0.4);
        color = mix(color, foam, foamMask * 0.7);
        float glitter = pow(max(0.0, f - 0.3), 3.0) * coverage;
        color += sunlight * glitter * 0.8;
        color *= smoothstep(2.5, 0.4, length(uv * 0.6));

        gl_FragColor = vec4(color, 1.0);
      }
    `;

    const init = () => {
      const THREE = window.THREE;
      scene = new THREE.Scene();
      camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'high-performance' });
      renderer.setSize(window.innerWidth, window.innerHeight);
      const maxPixelRatio = window.matchMedia('(max-width: 768px)').matches ? 1 : 1.5;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, maxPixelRatio));
      container.appendChild(renderer.domElement);

      const geometry = new THREE.PlaneGeometry(2, 2);
      const uniforms = {
        u_time: { value: 0.0 },
        u_resolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
        u_mouse: { value: new THREE.Vector2(0.5, 0.5) }
      };

      const material = new THREE.ShaderMaterial({ vertexShader, fragmentShader, uniforms });
      mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      resizeHandler = () => {
        renderer.setSize(window.innerWidth, window.innerHeight);
        uniforms.u_resolution.value.set(window.innerWidth, window.innerHeight);
        if (!isAnimated) {
          renderer.render(scene, camera);
        }
      };

      let mouseTargetX = 0.5;
      let mouseTargetY = 0.5;
      let lastMouseReport = 0;
      mouseMoveHandler = (event) => {
        const x = event.clientX / window.innerWidth;
        const y = 1.0 - event.clientY / window.innerHeight;
        mouseTargetX = x;
        mouseTargetY = y;
        const now = Date.now();
        if (now - lastMouseReport > 120) {
          onMouseTarget(`坐标: ${x.toFixed(3)}, ${y.toFixed(3)}`);
          lastMouseReport = now;
        }
      };

      window.addEventListener('resize', resizeHandler);
      if (!isAnimated) {
        uniforms.u_time.value = 0.35;
        renderer.render(scene, camera);
        onMouseTarget('坐标: 静态模式');
        return;
      }
      window.addEventListener('mousemove', mouseMoveHandler);
      visibilityHandler = () => {
        if (!document.hidden) {
          lastRenderTime = 0;
        }
      };
      document.addEventListener('visibilitychange', visibilityHandler);

      const clock = new THREE.Clock();
      let lastRenderTime = 0;
      const frameInterval = 1000 / 45;
      const animate = (timestamp = 0) => {
        animationFrame = window.requestAnimationFrame(animate);
        if (document.hidden) {
          return;
        }
        if (timestamp - lastRenderTime < frameInterval) {
          return;
        }
        lastRenderTime = timestamp;
        uniforms.u_mouse.value.x += (mouseTargetX - uniforms.u_mouse.value.x) * 0.08;
        uniforms.u_mouse.value.y += (mouseTargetY - uniforms.u_mouse.value.y) * 0.08;
        uniforms.u_time.value = clock.getElapsedTime();
        renderer.render(scene, camera);
      };
      animate();
    };

    const loadThree = () => {
      if (window.THREE) {
        init();
        return;
      }
      scriptTag = document.createElement('script');
      scriptTag.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
      scriptTag.onload = init;
      document.head.appendChild(scriptTag);
    };

    loadThree();

    return () => {
      if (animationFrame) {
        window.cancelAnimationFrame(animationFrame);
      }
      if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
      }
      if (mouseMoveHandler) {
        window.removeEventListener('mousemove', mouseMoveHandler);
      }
      if (visibilityHandler) {
        document.removeEventListener('visibilitychange', visibilityHandler);
      }
      if (renderer) {
        renderer.dispose();
        if (renderer.domElement && container.contains(renderer.domElement)) {
          container.removeChild(renderer.domElement);
        }
      }
      if (scriptTag && scriptTag.parentElement) {
        scriptTag.parentElement.removeChild(scriptTag);
      }
    };
  }, [containerRef, onMouseTarget, isAnimated]);
}
