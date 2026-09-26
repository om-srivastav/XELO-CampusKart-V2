// A self-contained decorative WebGL scene; content and CSS fallback do not depend on it.
export function mount(canvas) {
  const gl = canvas.getContext("webgl", {
    alpha: true,
    antialias: false,
    powerPreference: "low-power",
  });
  if (!gl) return;
  const shaders = [];
  function shader(type, source) {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw Error("shader");
    shaders.push(s);
    return s;
  }
  const program = gl.createProgram();
  try {
    gl.attachShader(
      program,
      shader(
        gl.VERTEX_SHADER,
        `attribute vec3 p; uniform float t; uniform vec2 mouse; uniform float aspect; varying float depth; void main(){float a=t*.12; vec3 v=vec3(p.x*cos(a)+p.z*sin(a),p.y,p.z*cos(a)-p.x*sin(a)); v.xy+=mouse*.12; float d=2.8+v.z; gl_Position=vec4(v.x/d/aspect,v.y/d,0.,1.); gl_PointSize=3.+(1.-v.z)*2.; depth=(1.-v.z)*.3+.2;}`,
      ),
    );
    gl.attachShader(
      program,
      shader(
        gl.FRAGMENT_SHADER,
        `precision mediump float; varying float depth; void main(){float d=length(gl_PointCoord-.5); if(d>.5)discard; gl_FragColor=vec4(.17,.7,.52,depth*(1.-d));}`,
      ),
    );
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
  } catch {
    return;
  }
  gl.useProgram(program);
  const vertices = [];
  for (let i = 0; i < 180; i++) {
    const y = 1 - (i / 179) * 2,
      r = Math.sqrt(1 - y * y),
      a = i * 2.39996;
    vertices.push(Math.cos(a) * r, y, Math.sin(a) * r);
  }
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
  const p = gl.getAttribLocation(program, "p");
  gl.enableVertexAttribArray(p);
  gl.vertexAttribPointer(p, 3, gl.FLOAT, false, 0, 0);
  const t = gl.getUniformLocation(program, "t"),
    mouse = gl.getUniformLocation(program, "mouse"),
    aspect = gl.getUniformLocation(program, "aspect");
  let visible = true,
    lost = false,
    last = 0,
    id = 0,
    x = 0,
    y = 0;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  function frame(now) {
    id = 0;
    if (!visible || document.hidden || reduced.matches || lost) return;
    if (now - last > 33) {
      last = now;
      const rect = canvas.getBoundingClientRect(),
        ratio = Math.min(devicePixelRatio, 1.5);
      const w = Math.round(rect.width * ratio),
        h = Math.round(rect.height * ratio);
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, w, h);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(t, now / 1000);
      gl.uniform2f(mouse, x, y);
      gl.uniform1f(aspect, w / Math.max(h, 1));
      gl.drawArrays(gl.POINTS, 0, 180);
    }
    id = requestAnimationFrame(frame);
  }
  function resume() {
    if (!id) id = requestAnimationFrame(frame);
  }
  const io = new IntersectionObserver((e) => {
    visible = e[0].isIntersecting;
    resume();
  });
  io.observe(canvas);
  const move = (e) => {
    x = e.clientX / innerWidth - 0.5;
    y = 0.5 - e.clientY / innerHeight;
  };
  if (matchMedia("(pointer: fine)").matches)
    window.addEventListener("pointermove", move, { passive: true });
  document.addEventListener("visibilitychange", resume);
  reduced.addEventListener("change", resume);
  canvas.addEventListener("webglcontextlost", (e) => {
    e.preventDefault();
    lost = true;
    cancelAnimationFrame(id);
  });
  window.addEventListener(
    "pagehide",
    () => {
      cancelAnimationFrame(id);
      io.disconnect();
      window.removeEventListener("pointermove", move);
      document.removeEventListener("visibilitychange", resume);
      reduced.removeEventListener("change", resume);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      shaders.forEach((s) => gl.deleteShader(s));
    },
    { once: true },
  );
  resume();
}
