(() => {
  "use strict";

  const CONFIG = {
    renderMode: "characters",
    bgMode: "solid",
    bgBlur: 12,
    bgOpacity: 90,
    cellSize: 16,
    coverage: 100,
    invert: false,
    styleBlend: "source-over",
    charSet: "binary",
    customChars: "",
    brightness: 18,
    contrast: 120,
    edgeEmphasis: 0,
    density: 0,
    toneCurve: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
    tint: "#3ca6ff",
    tintOpacity: 0,
    overlayBlend: "multiply",
    saturation: 100,
    grayscale: 0,
    blurType: "off",
    blurAmount: 35,
    blurAngle: 0,
    directionalBothSides: false,
    tiltFocus: 35,
    tiltPosition: 50,
    tiltFeather: 15,
    lensFocus: 40,
    blurCenterX: 50,
    blurCenterY: 50,
    progressivePosition: 55,
    progressiveReverse: false,
    pfx: {
      vignette: { enabled: true, intensity: 38 },
      scanLines: { enabled: true, intensity: 40 },
      chromatic: { enabled: false, intensity: 15 },
      bloom: { enabled: true, intensity: 20 },
      filmGrain: { enabled: true, intensity: 22 },
      glitch: { enabled: false, intensity: 20 },
      pixelate: { enabled: true, intensity: 15 },
      halftone: { enabled: true, intensity: 12 },
      filmDust: { enabled: false, intensity: 20 },
    },
    animated: false,
    animStyle: "flicker",
    animSpeed: { enabled: true, intensity: 100 },
    animIntensity: { enabled: true, intensity: 100 },
    lights: { enabled: false, points: [] },
    mask: {
      enabled: false,
      tool: "freehand",
      brushSize: 30,
      showOverlay: false,
      invert: false,
      dataUrl: null,
      shapes: [],
    },
    gradientSource: {
      mode: "radial",
      colors: [
        { id: "qsc_quark", name: "Quark Red", hex: "#AA1E2E", pos: 0 },
        { id: "qsc_quark_deep", name: "Deep Quark", hex: "#5B0D18", pos: 38 },
        { id: "qsc_force", name: "Force Blue", hex: "#131E29", pos: 70 },
        { id: "qsc_carbon", name: "Carbon", hex: "#020406", pos: 100 },
      ],
      angle: 90,
      centerX: 46,
      centerY: 52,
      scale: 88,
      softness: 26,
      wave: 12,
      distortion: 28,
      grain: 0,
      vignette: 0,
      count: 6,
      fade: 40,
      envelope: "ramp",
      spread: -20,
      soften: 0,
      pixelCols: 16,
      pixelRows: 10,
      pixelAngle: 45,
      pixelDither: 50,
      pixelGap: 0,
      archBase: 70,
      archHeight: 50,
      archWidth: 100,
      archGlow: 55,
      archEdge: 30,
      animated: false,
      speed: 50,
      motionAmount: 86,
      motionReverse: false,
      seed: 1,
      backdrop: "#131E29",
    },
  };

  const CHAR_SETS = {
    standard: " .:-=+*#%@",
    blocks: " ░▒▓█",
    binary: " 01",
    technical: " ·+x*#",
  };
  const TAU = Math.PI * 2;
  const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
  const lerp = (start, end, amount) => start + (end - start) * amount;
  const smoothstep = value => value * value * (3 - 2 * value);
  const rgba = (color, alpha = 1) =>
    `rgba(${Math.round(color.r)},${Math.round(color.g)},${Math.round(color.b)},${clamp(alpha)})`;

  function hexToRgb(hex) {
    const value = hex.replace("#", "");
    const normalized = value.length === 3
      ? value.split("").map(char => char + char).join("")
      : value;
    return {
      r: Number.parseInt(normalized.slice(0, 2), 16),
      g: Number.parseInt(normalized.slice(2, 4), 16),
      b: Number.parseInt(normalized.slice(4, 6), 16),
    };
  }

  function hash(x, y, seed = 1) {
    const value = Math.sin(x * 127.1 + y * 311.7 + seed * 74.7) * 43758.5453;
    return value - Math.floor(value);
  }

  function interpolateColor(start, end, amount) {
    return {
      r: lerp(start.r, end.r, amount),
      g: lerp(start.g, end.g, amount),
      b: lerp(start.b, end.b, amount),
    };
  }

  function toneMap(value, curve) {
    const input = clamp(value);
    for (let index = 1; index < curve.length; index += 1) {
      const left = curve[index - 1];
      const right = curve[index];
      if (input <= right.x) {
        const amount = clamp((input - left.x) / Math.max(.0001, right.x - left.x));
        return lerp(left.y, right.y, amount);
      }
    }
    return curve.at(-1)?.y ?? input;
  }

  function adjustedColor(input, config) {
    const brightness = config.brightness * 2.55;
    const contrast = config.contrast / 100;
    let r = (input.r - 128) * contrast + 128 + brightness;
    let g = (input.g - 128) * contrast + 128 + brightness;
    let b = (input.b - 128) * contrast + 128 + brightness;
    const luminance = .2126 * r + .7152 * g + .0722 * b;
    const saturation = config.saturation / 100;
    r = lerp(luminance, r, saturation);
    g = lerp(luminance, g, saturation);
    b = lerp(luminance, b, saturation);
    const grayAmount = config.grayscale / 100;
    r = lerp(r, luminance, grayAmount);
    g = lerp(g, luminance, grayAmount);
    b = lerp(b, luminance, grayAmount);
    if (config.tintOpacity > 0) {
      const tint = hexToRgb(config.tint);
      const amount = config.tintOpacity / 100;
      const blended = config.overlayBlend === "multiply"
        ? { r: r * tint.r / 255, g: g * tint.g / 255, b: b * tint.b / 255 }
        : interpolateColor({ r, g, b }, tint, .5);
      r = lerp(r, blended.r, amount);
      g = lerp(g, blended.g, amount);
      b = lerp(b, blended.b, amount);
    }
    return { r: clamp(r, 0, 255), g: clamp(g, 0, 255), b: clamp(b, 0, 255) };
  }

  function addEasedStops(gradient, stops) {
    const parsed = stops.map(stop => ({ ...stop, color: hexToRgb(stop.hex) }));
    for (let index = 0; index < parsed.length - 1; index += 1) {
      const start = parsed[index];
      const end = parsed[index + 1];
      const startPosition = start.pos / 100;
      const endPosition = end.pos / 100;
      const divisions = 8;
      for (let step = 0; step < divisions; step += 1) {
        const amount = step / divisions;
        gradient.addColorStop(
          lerp(startPosition, endPosition, amount),
          rgba(interpolateColor(start.color, end.color, smoothstep(amount))),
        );
      }
    }
    const last = parsed.at(-1);
    gradient.addColorStop(last.pos / 100, rgba(last.color));
  }

  function starPath(ctx, x, y, outerRadius, innerRadius, points = 5, rotation = -Math.PI / 2) {
    ctx.beginPath();
    for (let index = 0; index < points * 2; index += 1) {
      const radius = index % 2 === 0 ? outerRadius : innerRadius;
      const angle = rotation + index * Math.PI / points;
      const pointX = x + Math.cos(angle) * radius;
      const pointY = y + Math.sin(angle) * radius;
      if (index === 0) ctx.moveTo(pointX, pointY);
      else ctx.lineTo(pointX, pointY);
    }
    ctx.closePath();
  }

  class NeonNebula {
    constructor(canvas, config) {
      this.canvas = canvas;
      this.config = config;
      this.ctx = canvas.getContext("2d", { alpha: true });
      this.source = document.createElement("canvas");
      this.sourceCtx = this.source.getContext("2d", { alpha: false, willReadFrequently: true });
      this.sample = document.createElement("canvas");
      this.sampleCtx = this.sample.getContext("2d", { willReadFrequently: true });
      this.glyphs = document.createElement("canvas");
      this.glyphCtx = this.glyphs.getContext("2d");
      this.fx = document.createElement("canvas");
      this.fxCtx = this.fx.getContext("2d");
      this.pixel = document.createElement("canvas");
      this.pixelCtx = this.pixel.getContext("2d");
      this.maskLayer = document.createElement("canvas");
      this.maskLayerCtx = this.maskLayer.getContext("2d");
      this.maskImage = null;
      this.halftonePattern = null;
      this.binarySprites = new Map();
      this.width = 0;
      this.height = 0;
      this.cssWidth = 0;
      this.cssHeight = 0;
      this.pixelRatio = 1;
      this.cellSize = config.cellSize;
      this.cols = 0;
      this.rows = 0;
      this.averageRenderMs = 0;
      this.handleResize = this.handleResize.bind(this);
    }

    start() {
      if (!this.ctx || !this.sourceCtx || !this.sampleCtx || !this.glyphCtx || !this.fxCtx) return;
      window.addEventListener("resize", this.handleResize, { passive: true });
      if (this.config.mask.enabled && this.config.mask.dataUrl) {
        this.maskImage = new Image();
        this.maskImage.addEventListener("load", () => this.draw(0), { once: true });
        this.maskImage.src = this.config.mask.dataUrl;
      }
      this.resize();
      this.draw(0);
    }

    handleResize() {
      window.clearTimeout(this.resizeTimer);
      this.resizeTimer = window.setTimeout(() => {
        this.resize();
        this.draw(0);
      }, 120);
    }

    resize() {
      this.cssWidth = Math.max(320, window.innerWidth);
      this.cssHeight = Math.max(480, window.innerHeight);
      // Static rendering lets us spend the frame budget on a sharper backing
      // store. A 1.5× floor improves ordinary displays; Retina is capped at 2×
      // to avoid excessive memory use on large scientific workstations.
      this.pixelRatio = Math.min(2, Math.max(1.5, window.devicePixelRatio || 1));
      this.width = Math.ceil(this.cssWidth * this.pixelRatio);
      this.height = Math.ceil(this.cssHeight * this.pixelRatio);
      this.cellSize = this.config.cellSize * this.pixelRatio;
      this.cols = Math.ceil(this.width / this.cellSize);
      this.rows = Math.ceil(this.height / this.cellSize);
      this.canvas.width = this.width;
      this.canvas.height = this.height;
      this.canvas.dataset.pixelRatio = this.pixelRatio.toFixed(2);
      this.canvas.dataset.static = "true";
      this.glyphs.width = this.width;
      this.glyphs.height = this.height;
      this.fx.width = this.width;
      this.fx.height = this.height;
      this.maskLayer.width = this.width;
      this.maskLayer.height = this.height;
      this.source.width = this.width;
      this.source.height = this.height;
      this.sample.width = this.cols;
      this.sample.height = this.rows;
      this.binarySprites.clear();
      this.halftonePattern = null;
    }

    renderGradient(time) {
      const source = this.config.gradientSource;
      const ctx = this.sourceCtx;
      const width = this.source.width;
      const height = this.source.height;
      const speed = source.animated ? source.speed / 50 : 0;
      const direction = source.motionReverse ? -1 : 1;
      const seconds = time / 1000 * speed * direction;
      const motion = source.motionAmount / 100;
      const centerX = width * (
        source.centerX / 100
        + Math.sin(seconds * .37) * .055 * motion
        + Math.sin(seconds * .13 + 2.2) * .018 * motion
      );
      const centerY = height * (
        source.centerY / 100
        + Math.cos(seconds * .31) * .045 * motion
        + Math.sin(seconds * .19) * .015 * motion
      );
      const radius = Math.hypot(width, height) * source.scale / 100
        * (1 + Math.sin(seconds * .23) * source.wave / 300);
      const angle = source.angle * Math.PI / 180 + Math.sin(seconds * .21) * source.distortion / 400;

      ctx.save();
      ctx.fillStyle = source.colors.at(-1).hex;
      ctx.fillRect(0, 0, width, height);
      ctx.translate(centerX, centerY);
      ctx.rotate(angle);
      ctx.scale(1.16 + Math.sin(seconds * .17) * .05, .84 + Math.cos(seconds * .2) * .04);
      const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
      addEasedStops(gradient, source.colors);
      ctx.fillStyle = gradient;
      ctx.fillRect(-width * 2, -height * 2, width * 4, height * 4);
      ctx.restore();

      const deepQuark = hexToRgb(source.colors[1].hex);
      const quark = hexToRgb(source.colors[0].hex);
      ctx.save();
      ctx.globalCompositeOperation = "screen";
      for (let index = 0; index < 3; index += 1) {
        const phase = seconds * (.19 + index * .06) + index * 2.1;
        const x = centerX + Math.cos(phase) * width * .18 * motion;
        const y = centerY + Math.sin(phase * 1.17) * height * .16 * motion;
        const glowRadius = Math.max(width, height) * (.17 + index * .035);
        const glow = ctx.createRadialGradient(x, y, 0, x, y, glowRadius);
        const color = index === 0 ? quark : deepQuark;
        glow.addColorStop(0, rgba(color, .13 - index * .02));
        glow.addColorStop(1, rgba(color, 0));
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, width, height);
      }
      ctx.restore();
    }

    sampleGradient() {
      this.sampleCtx.imageSmoothingEnabled = true;
      this.sampleCtx.clearRect(0, 0, this.cols, this.rows);
      this.sampleCtx.drawImage(this.source, 0, 0, this.cols, this.rows);
      return this.sampleCtx.getImageData(0, 0, this.cols, this.rows).data;
    }

    cellSample(data, col, row) {
      const index = (row * this.cols + col) * 4;
      return { r: data[index], g: data[index + 1], b: data[index + 2] };
    }

    cellLuminance(data, col, row) {
      const color = this.cellSample(
        data,
        clamp(col, 0, this.cols - 1),
        clamp(row, 0, this.rows - 1),
      );
      return (.2126 * color.r + .7152 * color.g + .0722 * color.b) / 255;
    }

    animatedPosition(x, y, time) {
      if (!this.config.animated) return { x, y, alpha: 1, scale: 1 };
      const speed = this.config.animSpeed.enabled ? this.config.animSpeed.intensity / 100 : 0;
      const intensity = this.config.animIntensity.enabled ? this.config.animIntensity.intensity / 100 : 0;
      const phase = time / 1000 * speed;
      switch (this.config.animStyle) {
        case "pulse":
          return { x, y, alpha: .8 + Math.sin(phase * 2.2 + x * .01) * .2 * intensity, scale: 1 + Math.sin(phase * 2 + y * .02) * .18 * intensity };
        case "shimmer":
          return { x: x + Math.sin(phase * 1.8 + y * .035) * 2 * intensity, y, alpha: .75 + Math.sin(phase * 3 + x * .025) * .25 * intensity, scale: 1 };
        case "ripple": {
          const distance = Math.hypot(x - this.width / 2, y - this.height / 2);
          const ripple = Math.sin(distance * .025 - phase * 3) * intensity;
          return { x, y: y + ripple * 3, alpha: .82 + ripple * .18, scale: 1 + ripple * .12 };
        }
        case "flicker":
          {
            const cellPhase = hash(x, y, 37);
            const cadence = 1.1 + cellPhase * 1.9;
            const wave = (Math.sin(phase * cadence * TAU + cellPhase * TAU) + 1) / 2;
            const presence = smoothstep(clamp((wave - .16) / .68));
            return {
              x,
              y,
              alpha: lerp(1, .018 + presence * .982, intensity),
              scale: 1,
            };
          }
        case "wave":
        default:
          return {
            x: x + Math.cos(y * .018 + phase * .75) * 1.5 * intensity,
            y: y + Math.sin(x * .014 + phase * 1.15) * 3.8 * intensity,
            alpha: .82 + Math.sin(x * .01 + y * .008 + phase) * .18 * intensity,
            scale: 1 + Math.sin(x * .012 - phase * .8) * .1 * intensity,
          };
      }
    }

    binarySprite(glyph, luminance, size) {
      const region = luminance > .15 ? "light" : "dark";
      const spriteSize = Math.ceil(size * 1.55);
      const key = `${region}-${glyph}-${spriteSize}`;
      if (this.binarySprites.has(key)) return this.binarySprites.get(key);

      const sprite = document.createElement("canvas");
      sprite.width = spriteSize;
      sprite.height = spriteSize;
      const spriteCtx = sprite.getContext("2d");
      const color = region === "light"
        ? (glyph === "1" ? "#131E29" : "#5B0D18")
        : (glyph === "1" ? "#CFD2D3" : "#AA1E2E");
      spriteCtx.fillStyle = color;
      spriteCtx.shadowColor = glyph === "1" ? "rgba(207,210,211,.28)" : "rgba(170,30,46,.34)";
      spriteCtx.shadowBlur = 3;
      spriteCtx.font = `700 ${Math.max(10, size * .72)}px ui-monospace, "SFMono-Regular", monospace`;
      spriteCtx.textAlign = "center";
      spriteCtx.textBaseline = "middle";
      spriteCtx.fillText(glyph, spriteSize / 2, spriteSize / 2);
      this.binarySprites.set(key, sprite);
      return sprite;
    }

    drawPrimitive(ctx, mode, x, y, size, luminance, color, col, row, time) {
      const alpha = clamp(.22 + luminance * .88);
      const fill = rgba(color, alpha);
      const stroke = rgba(color, clamp(.18 + luminance * .72));
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = Math.max(1, size * .08);
      const radius = Math.max(1.2, size * (.12 + luminance * .34));

      if (mode === "mixed") {
        const modes = ["dots", "cross", "diamond", "stars", "rings", "lines"];
        this.drawPrimitive(ctx, modes[Math.floor(hash(col, row, 8) * modes.length)], x, y, size, luminance, color, col, row, time);
        return;
      }
      if (mode === "characters" || mode === "hexdump" || mode === "matrix" || mode === "braille") {
        let glyphs = this.config.customChars || CHAR_SETS[this.config.charSet] || CHAR_SETS.standard;
        let glyph = glyphs[Math.min(glyphs.length - 1, Math.floor(luminance * glyphs.length))];
        const binary = mode === "characters" && this.config.charSet === "binary";
        if (binary) {
          const epoch = Math.floor(time / 850 + hash(col, row, 41) * 4);
          glyph = hash(col, row, epoch + 43) > .5 ? "1" : "0";
          const sprite = this.binarySprite(glyph, luminance, size);
          ctx.drawImage(sprite, x - sprite.width / 2, y - sprite.height / 2);
          return;
        }
        if (mode === "hexdump") glyph = "0123456789ABCDEF"[Math.floor(luminance * 15)];
        if (mode === "matrix") {
          glyph = "01アイウエオカキクケコサシスセソ"[Math.floor(hash(col, row + Math.floor(time / 90), 4) * 22)];
          ctx.fillStyle = `rgba(89,255,156,${clamp(.18 + luminance * .8)})`;
        }
        if (mode === "braille") glyph = String.fromCodePoint(0x2800 + Math.floor(luminance * 255));
        ctx.font = binary
          ? `700 ${Math.max(10, size * (.64 + luminance * .16))}px ui-monospace, "SFMono-Regular", monospace`
          : `${Math.max(7, radius * 2.2)}px ui-monospace, monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(glyph, x, y);
        return;
      }
      if (mode === "dither") {
        const matrix = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];
        if (luminance * 16 > matrix[row % 4][col % 4]) ctx.fillRect(x - size * .34, y - size * .34, size * .68, size * .68);
        return;
      }
      if (["mosaic", "pixel", "lego"].includes(mode)) {
        const extent = size * (.2 + luminance * .28);
        ctx.fillRect(x - extent, y - extent, extent * 2, extent * 2);
        if (mode === "lego") {
          ctx.fillStyle = rgba({ r: 255, g: 255, b: 255 }, .14);
          ctx.beginPath();
          ctx.arc(x, y - extent * .3, extent * .28, 0, TAU);
          ctx.fill();
        }
        return;
      }
      if (mode === "dots" || mode === "bubbles" || mode === "rings") {
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, TAU);
        if (mode === "dots") ctx.fill();
        else ctx.stroke();
        if (mode === "bubbles") {
          ctx.fillStyle = "rgba(255,255,255,.25)";
          ctx.beginPath();
          ctx.arc(x - radius * .3, y - radius * .3, Math.max(1, radius * .16), 0, TAU);
          ctx.fill();
        }
        return;
      }
      if (mode === "cross" || mode === "lines" || mode === "diagonal" || mode === "hatch") {
        ctx.beginPath();
        if (mode === "cross") {
          ctx.moveTo(x - radius, y); ctx.lineTo(x + radius, y);
          ctx.moveTo(x, y - radius); ctx.lineTo(x, y + radius);
        } else {
          ctx.moveTo(x - radius, y + radius); ctx.lineTo(x + radius, y - radius);
          if (mode === "hatch") {
            ctx.moveTo(x - radius, y - radius); ctx.lineTo(x + radius, y + radius);
          }
        }
        ctx.stroke();
        return;
      }
      if (mode === "diamond") {
        ctx.beginPath();
        ctx.moveTo(x, y - radius); ctx.lineTo(x + radius, y);
        ctx.lineTo(x, y + radius); ctx.lineTo(x - radius, y);
        ctx.closePath(); ctx.fill();
        return;
      }
      if (mode === "voxel") {
        const r = radius * .9;
        ctx.beginPath();
        ctx.moveTo(x, y - r); ctx.lineTo(x + r, y - r * .45);
        ctx.lineTo(x, y + r * .1); ctx.lineTo(x - r, y - r * .45);
        ctx.closePath(); ctx.fill();
        ctx.globalAlpha *= .7;
        ctx.beginPath();
        ctx.moveTo(x - r, y - r * .45); ctx.lineTo(x, y + r * .1);
        ctx.lineTo(x, y + r); ctx.lineTo(x - r, y + r * .45);
        ctx.closePath(); ctx.fill();
        ctx.globalAlpha = 1;
        return;
      }
      if (mode === "disco") {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(time / 900 + (col + row) * .17);
        ctx.fillRect(-radius, -radius, radius * 2, radius * 2);
        ctx.restore();
        return;
      }
      if (mode === "hearts") {
        const r = radius * .82;
        ctx.beginPath();
        ctx.moveTo(x, y + r);
        ctx.bezierCurveTo(x - r * 1.7, y, x - r, y - r, x, y - r * .25);
        ctx.bezierCurveTo(x + r, y - r, x + r * 1.7, y, x, y + r);
        ctx.fill();
        return;
      }
      if (mode === "hexagons") {
        ctx.beginPath();
        for (let index = 0; index < 6; index += 1) {
          const angle = Math.PI / 3 * index;
          const px = x + Math.cos(angle) * radius;
          const py = y + Math.sin(angle) * radius;
          if (index === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath(); ctx.stroke();
        return;
      }
      if (mode === "triangles") {
        const direction = (col + row) % 2 ? 1 : -1;
        ctx.beginPath();
        ctx.moveTo(x, y - radius * direction);
        ctx.lineTo(x + radius, y + radius * direction);
        ctx.lineTo(x - radius, y + radius * direction);
        ctx.closePath(); ctx.fill();
        return;
      }
      if (mode === "contour") {
        const band = Math.round(luminance * 8) / 8;
        if (Math.abs(luminance - band) < .035) {
          ctx.beginPath();
          ctx.arc(x, y, radius * 1.4, Math.PI * .15, Math.PI * 1.25);
          ctx.stroke();
        }
        return;
      }
      if (mode === "halfblocks") {
        ctx.fillRect(x - size * .34, y - size * .4, size * .68, size * .38);
        ctx.globalAlpha = .55;
        ctx.fillRect(x - size * .34, y + size * .02, size * .68, size * .38);
        ctx.globalAlpha = 1;
        return;
      }

      starPath(ctx, x, y, radius * 1.15, radius * .42, 5, -Math.PI / 2 + hash(col, row, 2) * .35);
      ctx.fill();
    }

    renderCells(data, time) {
      const ctx = this.glyphCtx;
      const size = this.cellSize;
      const coverage = clamp((this.config.coverage + this.config.density * .25) / 100);
      ctx.clearRect(0, 0, this.width, this.height);
      ctx.globalCompositeOperation = this.config.styleBlend;

      for (let row = 0; row < this.rows; row += 1) {
        for (let col = 0; col < this.cols; col += 1) {
          if (hash(col, row, this.config.gradientSource.seed) > coverage) continue;
          const sourceColor = this.cellSample(data, col, row);
          let luminance = this.cellLuminance(data, col, row);
          if (this.config.edgeEmphasis > 0) {
            const edge = Math.abs(luminance - this.cellLuminance(data, col + 1, row))
              + Math.abs(luminance - this.cellLuminance(data, col, row + 1));
            luminance = clamp(luminance + edge * this.config.edgeEmphasis / 100);
          }
          luminance = toneMap(this.config.invert ? 1 - luminance : luminance, this.config.toneCurve);
          const color = adjustedColor(sourceColor, this.config);
          const baseX = col * size + size / 2;
          const baseY = row * size + size / 2;
          const animated = this.animatedPosition(baseX, baseY, time);
          ctx.save();
          ctx.globalAlpha = clamp(animated.alpha);
          this.drawPrimitive(
            ctx,
            this.config.renderMode,
            animated.x,
            animated.y,
            size * animated.scale,
            luminance,
            color,
            col,
            row,
            time,
          );
          ctx.restore();
        }
      }
      ctx.globalCompositeOperation = "source-over";
    }

    drawBackground() {
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.width, this.height);
      ctx.fillStyle = this.config.gradientSource.colors.at(-1).hex;
      ctx.fillRect(0, 0, this.width, this.height);
      ctx.save();
      ctx.globalAlpha = this.config.bgOpacity / 100;
      const blur = Math.max(0, this.config.bgBlur) * this.pixelRatio;
      ctx.filter = `blur(${blur}px) saturate(118%)`;
      const overscan = blur * 2;
      ctx.drawImage(
        this.source,
        -overscan,
        -overscan,
        this.width + overscan * 2,
        this.height + overscan * 2,
      );
      ctx.restore();
    }

    compositeGlyphs() {
      const ctx = this.ctx;
      ctx.save();
      if (this.config.blurType !== "off") {
        const blur = Math.max(0, this.config.blurAmount / 10);
        ctx.filter = `blur(${blur}px)`;
      }
      ctx.drawImage(this.glyphs, 0, 0);
      ctx.restore();
    }

    copyToFx() {
      this.fxCtx.clearRect(0, 0, this.width, this.height);
      this.fxCtx.drawImage(this.canvas, 0, 0);
    }

    applyPostEffects(time) {
      const effects = this.config.pfx;
      const ctx = this.ctx;

      if (effects.bloom.enabled) {
        this.copyToFx();
        ctx.save();
        ctx.globalCompositeOperation = "screen";
        ctx.globalAlpha = effects.bloom.intensity / 260;
        ctx.filter = `blur(${4 + effects.bloom.intensity * .16}px)`;
        ctx.drawImage(this.fx, 0, 0);
        ctx.restore();
      }

      if (effects.chromatic.enabled) {
        this.copyToFx();
        const offset = 1 + effects.chromatic.intensity / 12;
        ctx.save();
        ctx.globalCompositeOperation = "screen";
        ctx.globalAlpha = effects.chromatic.intensity / 250;
        ctx.drawImage(this.fx, offset, 0);
        ctx.drawImage(this.fx, -offset, 0);
        ctx.restore();
      }

      if (effects.glitch.enabled && Math.sin(time * .003) > .84) {
        this.copyToFx();
        const amount = effects.glitch.intensity / 100;
        for (let index = 0; index < 4; index += 1) {
          const y = hash(index, Math.floor(time / 120), 3) * this.height;
          const height = 2 + hash(index, 9, 4) * 18;
          const offset = (hash(index, 4, time) - .5) * 40 * amount;
          ctx.drawImage(this.fx, 0, y, this.width, height, offset, y, this.width, height);
        }
      }

      if (effects.halftone.enabled) {
        const intensity = effects.halftone.intensity / 100;
        if (!this.halftonePattern) {
          const tile = document.createElement("canvas");
          const tileSize = Math.max(8, Math.round(8 * this.pixelRatio));
          tile.width = tileSize;
          tile.height = tileSize;
          const tileCtx = tile.getContext("2d");
          tileCtx.fillStyle = "rgba(2,4,6,1)";
          tileCtx.beginPath();
          tileCtx.arc(tileSize / 2, tileSize / 2, 1.2 * this.pixelRatio, 0, TAU);
          tileCtx.fill();
          this.halftonePattern = ctx.createPattern(tile, "repeat");
        }
        ctx.save();
        ctx.globalAlpha = .08 * intensity;
        ctx.fillStyle = this.halftonePattern;
        ctx.fillRect(0, 0, this.width, this.height);
        ctx.restore();
      }

      if (effects.pixelate.enabled) {
        const block = Math.max(1, Math.round((1 + effects.pixelate.intensity / 12) * this.pixelRatio));
        const width = Math.max(1, Math.ceil(this.width / block));
        const height = Math.max(1, Math.ceil(this.height / block));
        if (this.pixel.width !== width) this.pixel.width = width;
        if (this.pixel.height !== height) this.pixel.height = height;
        this.pixelCtx.imageSmoothingEnabled = true;
        this.pixelCtx.drawImage(this.canvas, 0, 0, width, height);
        ctx.save();
        ctx.imageSmoothingEnabled = false;
        ctx.globalAlpha = .28 + effects.pixelate.intensity / 140;
        ctx.drawImage(this.pixel, 0, 0, width, height, 0, 0, this.width, this.height);
        ctx.restore();
        ctx.imageSmoothingEnabled = true;
      }

      if (effects.scanLines.enabled) {
        ctx.save();
        ctx.fillStyle = `rgba(2,4,6,${effects.scanLines.intensity / 560})`;
        const interval = Math.max(4, Math.round(4 * this.pixelRatio));
        const lineWidth = Math.max(1, Math.round(this.pixelRatio));
        for (let y = lineWidth; y < this.height; y += interval) {
          ctx.fillRect(0, y, this.width, lineWidth);
        }
        ctx.restore();
      }

      if (effects.filmGrain.enabled) {
        const count = Math.floor(
          this.width * this.height / (650 * this.pixelRatio * this.pixelRatio),
        );
        const opacity = effects.filmGrain.intensity / 950;
        const frameSeed = Math.floor(time / 80);
        ctx.save();
        for (let index = 0; index < count; index += 1) {
          const x = hash(index, frameSeed, 11) * this.width;
          const y = hash(index, frameSeed, 17) * this.height;
          ctx.fillStyle = hash(index, frameSeed, 19) > .5
            ? `rgba(255,255,255,${opacity})`
            : `rgba(2,4,6,${opacity})`;
          ctx.fillRect(x, y, 1, 1);
        }
        ctx.restore();
      }

      if (effects.filmDust.enabled) {
        const count = Math.ceil(effects.filmDust.intensity / 8);
        ctx.save();
        ctx.strokeStyle = `rgba(255,255,255,${effects.filmDust.intensity / 500})`;
        for (let index = 0; index < count; index += 1) {
          const x = hash(index, Math.floor(time / 200), 21) * this.width;
          const y = hash(index, 6, 22) * this.height;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + hash(index, 7, 23) * 4, y + 3 + hash(index, 8, 24) * 15);
          ctx.stroke();
        }
        ctx.restore();
      }

      if (effects.vignette.enabled) {
        const intensity = effects.vignette.intensity / 100;
        const vignette = ctx.createRadialGradient(
          this.width * .48,
          this.height * .46,
          Math.min(this.width, this.height) * .16,
          this.width * .5,
          this.height * .5,
          Math.max(this.width, this.height) * .72,
        );
        vignette.addColorStop(0, "rgba(2,4,6,0)");
        vignette.addColorStop(1, `rgba(2,4,6,${.78 * intensity})`);
        ctx.fillStyle = vignette;
        ctx.fillRect(0, 0, this.width, this.height);
      }
    }

    applyLights() {
      if (!this.config.lights.enabled) return;
      const ctx = this.ctx;
      ctx.save();
      ctx.globalCompositeOperation = "screen";
      this.config.lights.points.forEach(point => {
        const x = point.x * this.width;
        const y = point.y * this.height;
        const radius = point.radius * Math.max(this.width, this.height);
        const light = ctx.createRadialGradient(x, y, 0, x, y, radius);
        light.addColorStop(0, `rgba(170,30,46,${clamp(point.intensity / 100)})`);
        light.addColorStop(1, "rgba(170,30,46,0)");
        ctx.fillStyle = light;
        ctx.fillRect(0, 0, this.width, this.height);
      });
      ctx.restore();
    }

    applyMask() {
      if (!this.config.mask.enabled || !this.maskImage?.complete || !this.maskImage.naturalWidth) return;
      const maskCtx = this.maskLayerCtx;
      maskCtx.clearRect(0, 0, this.width, this.height);
      if (this.config.mask.invert) {
        maskCtx.fillStyle = "#fff";
        maskCtx.fillRect(0, 0, this.width, this.height);
        maskCtx.globalCompositeOperation = "destination-out";
        maskCtx.drawImage(this.maskImage, 0, 0, this.width, this.height);
      } else {
        maskCtx.drawImage(this.maskImage, 0, 0, this.width, this.height);
      }
      maskCtx.globalCompositeOperation = "source-over";

      this.fxCtx.clearRect(0, 0, this.width, this.height);
      this.fxCtx.drawImage(this.source, 0, 0, this.width, this.height);
      this.fxCtx.globalCompositeOperation = "destination-in";
      this.fxCtx.drawImage(this.maskLayer, 0, 0);
      this.fxCtx.globalCompositeOperation = "source-over";
      this.ctx.drawImage(this.fx, 0, 0);
    }

    draw(time) {
      if (!this.width || !this.height) return;
      const startedAt = performance.now();
      this.renderGradient(time);
      const data = this.sampleGradient();
      this.renderCells(data, time);
      this.drawBackground();
      this.compositeGlyphs();
      this.applyPostEffects(time);
      this.applyLights();
      this.applyMask();
      const renderMs = performance.now() - startedAt;
      this.averageRenderMs = this.averageRenderMs
        ? this.averageRenderMs * .86 + renderMs * .14
        : renderMs;
      this.canvas.dataset.renderMs = this.averageRenderMs.toFixed(2);
    }
  }

  const canvas = document.querySelector("#neon-nebula");
  if (canvas) new NeonNebula(canvas, CONFIG).start();
})();
