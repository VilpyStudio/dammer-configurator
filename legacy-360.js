(function () {
  var FRAME_COUNT = 8;
  var IMAGE_WIDTH = 1280;
  var IMAGE_HEIGHT = 900;
  var IMAGE_VERSION = "13";
  var PIXELS_PER_FRAME = 48;
  var INERTIA_FRICTION = 0.9;
  var MIN_VELOCITY = 0.002;

  var colors = {
    hull: [
      { name: "RAL 9010", value: "#f1ede1", asset: "ral9010" },
      { name: "RAL 1013", value: "#e3d9c6", asset: "ral1013" },
      { name: "RAL 6034", value: "#7fb5b5", asset: "ral6034" },
      { name: "RAL 7033", value: "#7d8471", asset: "ral7033" },
      { name: "RAL 7034", value: "#928e85", asset: "ral7034" },
      { name: "RAL 7038", value: "#b5b8b1", asset: "ral7038" },
      { name: "RAL 7039", value: "#6c6960", asset: "ral7039" }
    ],
    cushions: [
      { name: "Cognac", value: "#b96936", render: "#bd6b37", shade: { shadow: 0.48, range: 0.58, lift: 0.02, specular: 0.07, alphaBase: 24, alphaScale: 1.36 } },
      { name: "Creme", value: "#d8ccb4", render: "#d8cbb2", shade: { shadow: 0.60, range: 0.42, lift: 0.06, specular: 0.05, alphaBase: 18, alphaScale: 1.22 } },
      { name: "Taupe", value: "#877768", render: "#87786a", shade: { shadow: 0.50, range: 0.52, lift: 0.03, specular: 0.05, alphaBase: 20, alphaScale: 1.28 } },
      { name: "Donkerbruin", value: "#49362d", render: "#4e382f", shade: { shadow: 0.48, range: 0.62, lift: 0.00, specular: 0.05, alphaBase: 24, alphaScale: 1.36 } },
      { name: "Marine", value: "#293f55", render: "#2c4359", shade: { shadow: 0.48, range: 0.60, lift: 0.00, specular: 0.05, alphaBase: 24, alphaScale: 1.36 } },
      { name: "Lichtgrijs", value: "#b7b8b5", render: "#b7b8b4", shade: { shadow: 0.58, range: 0.44, lift: 0.05, specular: 0.04, alphaBase: 18, alphaScale: 1.22 } }
    ],
    teak: [
      { name: "Naturel teak", value: "#c98f4d", render: "#c58b4a", shade: { shadow: 0.46, range: 0.62, lift: 0.02, specular: 0.08, alphaBase: 12, alphaScale: 1.18 } },
      { name: "Honing teak", value: "#d6a864", render: "#d1a05e", shade: { shadow: 0.48, range: 0.58, lift: 0.03, specular: 0.08, alphaBase: 12, alphaScale: 1.16 } },
      { name: "Licht eiken", value: "#d4bd91", render: "#d3bd91", shade: { shadow: 0.55, range: 0.48, lift: 0.04, specular: 0.07, alphaBase: 10, alphaScale: 1.12 } },
      { name: "Vergrijsd teak", value: "#928b7b", render: "#928b7d", shade: { shadow: 0.50, range: 0.52, lift: 0.02, specular: 0.06, alphaBase: 10, alphaScale: 1.14 } }
    ]
  };

  var state = { hull: null, cushions: null, teak: null };
  var canvas = document.querySelector("canvas");
  var context = canvas && canvas.getContext ? canvas.getContext("2d") : null;
  var layerCanvas = document.createElement("canvas");
  layerCanvas.width = IMAGE_WIDTH;
  layerCanvas.height = IMAGE_HEIGHT;
  var layerContext = layerCanvas.getContext("2d");
  var stage = document.querySelector("[data-stage]");
  var loader = document.querySelector("[data-loader]");
  var downloadButton = document.querySelector("[data-download]");
  var resetButton = document.querySelector("[data-reset]");
  var images = {};
  var frameCache = {};
  var frameCacheKeys = [];
  var currentFrame = 0;
  var framePosition = 0;
  var renderedFrame = -1;
  var dragStartX = 0;
  var dragStartFrame = 0;
  var dragging = false;
  var lastDragX = 0;
  var lastDragTime = 0;
  var frameVelocity = 0;
  var inertiaFrame = 0;
  var currentShade = null;

  if (!canvas || !context || !stage) return;

  window.requestAnimationFrame = window.requestAnimationFrame || function (callback) {
    return window.setTimeout(function () { callback(now()); }, 16);
  };
  window.cancelAnimationFrame = window.cancelAnimationFrame || window.clearTimeout;

  function now() {
    return window.performance && performance.now ? performance.now() : new Date().getTime();
  }

  function frameName(frame) {
    return frame < 10 ? "0" + frame : String(frame);
  }

  function imagePath(layer, frame) {
    return "images/360-8/" + layer + "-" + frameName(frame) + ".png?v=" + IMAGE_VERSION;
  }

  function hullImagePath(colorKey, frame) {
    return "images/360-hull/hull-" + colorKey + "-" + frameName(frame) + ".png?v=" + IMAGE_VERSION;
  }

  function loadImage(src, done) {
    var image = new Image();
    image.onload = function () { done(null, image); };
    image.onerror = function () { done(true); };
    image.src = src;
  }

  function loadFrames(done) {
    var queue = [];
    var layers = ["base", "cushions", "teak"];
    var loaded = 0;
    var index = 0;
    var i;
    var frame;

    for (i = 0; i < layers.length; i += 1) {
      images[layers[i]] = [];
      for (frame = 0; frame < FRAME_COUNT; frame += 1) {
        queue.push({ role: layers[i], frame: frame, src: imagePath(layers[i], frame) });
      }
    }

    images.hull = {};
    for (i = 0; i < colors.hull.length; i += 1) {
      images.hull[colors.hull[i].asset] = [];
      for (frame = 0; frame < FRAME_COUNT; frame += 1) {
        queue.push({ role: "hull", asset: colors.hull[i].asset, frame: frame, src: hullImagePath(colors.hull[i].asset, frame) });
      }
    }

    function next() {
      var item = queue[index];
      if (!item) {
        done();
        return;
      }
      loadImage(item.src, function (error, image) {
        if (error) {
          done(error);
          return;
        }
        if (item.role === "hull") images.hull[item.asset][item.frame] = image;
        else images[item.role][item.frame] = image;
        loaded += 1;
        if (loader) loader.innerHTML = "Dammer renders worden geladen... " + Math.round((loaded / queue.length) * 100) + "%";
        index += 1;
        next();
      });
    }

    next();
  }

  function hexToRgb(hex) {
    var clean = hex.replace("#", "");
    return {
      r: parseInt(clean.slice(0, 2), 16),
      g: parseInt(clean.slice(2, 4), 16),
      b: parseInt(clean.slice(4, 6), 16)
    };
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function normalizedFrame(frame) {
    return ((frame % FRAME_COUNT) + FRAME_COUNT) % FRAME_COUNT;
  }

  function clearFrameCache() {
    frameCache = {};
    frameCacheKeys = [];
  }

  function nearestFrame(position) {
    return normalizedFrame(Math.round(position));
  }

  function findColor(role, value) {
    var list = colors[role];
    var i;
    for (i = 0; i < list.length; i += 1) {
      if (list[i].value === value) return list[i];
    }
    return null;
  }

  function layerToneRange(pixels) {
    var histogram = [];
    var total = 0;
    var index;
    var luma;
    var seen;
    var value;
    var low = 0;
    var high = 255;
    var lowTarget;
    var highTarget;

    for (index = 0; index < 256; index += 1) histogram[index] = 0;

    for (index = 0; index < pixels.length; index += 4) {
      if (pixels[index + 3] < 8) continue;
      luma = Math.round(pixels[index] * 0.2126 + pixels[index + 1] * 0.7152 + pixels[index + 2] * 0.0722);
      histogram[luma] += 1;
      total += 1;
    }

    if (!total) return { low: 0, high: 255 };

    lowTarget = total * 0.03;
    highTarget = total * 0.985;
    seen = 0;

    for (value = 0; value < 256; value += 1) {
      seen += histogram[value];
      if (seen >= lowTarget) {
        low = value;
        break;
      }
    }

    seen = 0;
    for (value = 0; value < 256; value += 1) {
      seen += histogram[value];
      if (seen >= highTarget) {
        high = value;
        break;
      }
    }

    return { low: low, high: Math.max(high, low + 24) };
  }

  function shadeColor(targetRgb, shade, layer) {
    var targetBrightness = (targetRgb.r * 0.2126 + targetRgb.g * 0.7152 + targetRgb.b * 0.0722) / 255;
    var lightColorBoost = clamp((targetBrightness - 0.66) / 0.34, 0, 1);
    var profile = currentShade || {
      hull: { shadow: 0.38, range: 0.64, lift: 0.03, specular: 0.17 },
      cushions: { shadow: 0.48, range: 0.58, lift: 0.07, specular: 0.12 },
      teak: { shadow: 0.44, range: 0.72, lift: 0.04, specular: 0.16 }
    }[layer] || { shadow: 0.38, range: 0.72, lift: 0.06, specular: 0.16 };
    var shadow = profile.shadow + (layer === "hull" ? lightColorBoost * 0.22 : 0);
    var range = profile.range - (layer === "hull" ? lightColorBoost * 0.12 : 0);
    var lift = profile.lift + (layer === "hull" ? lightColorBoost * 0.12 : 0);
    var brightness = shadow + Math.pow(shade, 0.82) * range;
    var highlight = Math.pow(clamp((shade - 0.76) / 0.24, 0, 1), 2) * profile.specular;

    return {
      r: Math.round(clamp(targetRgb.r * brightness + 255 * highlight + 255 * lift * (1 - shade), 0, 255)),
      g: Math.round(clamp(targetRgb.g * brightness + 255 * highlight + 255 * lift * (1 - shade), 0, 255)),
      b: Math.round(clamp(targetRgb.b * brightness + 255 * highlight + 255 * lift * (1 - shade), 0, 255))
    };
  }

  function tintLayer(layer, color, frame, targetContext) {
    var colorSpec = findColor(layer, color);
    var targetRgb = hexToRgb((colorSpec && colorSpec.render) || color);
    var data;
    var pixels;
    var toneRange;
    var index;
    var luma;
    var shade;
    var shaded;

    layerContext.clearRect(0, 0, IMAGE_WIDTH, IMAGE_HEIGHT);
    layerContext.drawImage(images[layer][frame], 0, 0);
    currentShade = colorSpec && colorSpec.shade ? colorSpec.shade : null;
    data = layerContext.getImageData(0, 0, IMAGE_WIDTH, IMAGE_HEIGHT);
    pixels = data.data;
    toneRange = layerToneRange(pixels);

    for (index = 0; index < pixels.length; index += 4) {
      if (pixels[index + 3] < 8) continue;
      luma = pixels[index] * 0.2126 + pixels[index + 1] * 0.7152 + pixels[index + 2] * 0.0722;
      shade = clamp((luma - toneRange.low) / (toneRange.high - toneRange.low), 0, 1);
      shaded = shadeColor(targetRgb, shade, layer);
      pixels[index] = shaded.r;
      pixels[index + 1] = shaded.g;
      pixels[index + 2] = shaded.b;
      if (currentShade && typeof currentShade.alphaScale === "number") {
        pixels[index + 3] = Math.round(clamp((currentShade.alphaBase || 0) + pixels[index + 3] * currentShade.alphaScale, 0, 255));
      }
    }

    layerContext.putImageData(data, 0, 0);
    targetContext.drawImage(layerCanvas, 0, 0);
    currentShade = null;
  }

  function frameCacheKey(frame) {
    return [frame, state.hull || "original", state.cushions || "original", state.teak || "original"].join("|");
  }

  function compositeFrame(frame) {
    var key = frameCacheKey(frame);
    var output;
    var outputContext;
    var hull = findColor("hull", state.hull);
    var hullRender = hull && images.hull && images.hull[hull.asset];

    if (frameCache[key]) return frameCache[key];
    output = document.createElement("canvas");
    output.width = IMAGE_WIDTH;
    output.height = IMAGE_HEIGHT;
    outputContext = output.getContext("2d");
    outputContext.drawImage(hullRender ? hullRender[frame] : images.base[frame], 0, 0);
    if (state.cushions) tintLayer("cushions", state.cushions, frame, outputContext);
    if (state.teak) tintLayer("teak", state.teak, frame, outputContext);

    frameCache[key] = output;
    frameCacheKeys.push(key);
    if (frameCacheKeys.length > FRAME_COUNT * 2) {
      delete frameCache[frameCacheKeys.shift()];
    }
    return output;
  }

  function draw(position, force) {
    var frame;
    if (!images.base) return;
    if (typeof position !== "number") position = framePosition;
    frame = nearestFrame(position);
    if (!force && frame === renderedFrame) return;
    context.clearRect(0, 0, IMAGE_WIDTH, IMAGE_HEIGHT);
    context.drawImage(compositeFrame(frame), 0, 0);
    currentFrame = frame;
    renderedFrame = frame;
  }

  function setFrame(frame) {
    framePosition = normalizedFrame(frame);
    currentFrame = nearestFrame(framePosition);
    draw(framePosition, true);
  }

  function stopInertia() {
    if (inertiaFrame) cancelAnimationFrame(inertiaFrame);
    inertiaFrame = 0;
  }

  function runInertia() {
    if (dragging) return;
    frameVelocity *= INERTIA_FRICTION;
    if (Math.abs(frameVelocity) < MIN_VELOCITY) {
      framePosition = nearestFrame(framePosition);
      draw(framePosition, true);
      stopInertia();
      return;
    }
    framePosition = normalizedFrame(framePosition + frameVelocity * 16.67);
    draw();
    inertiaFrame = requestAnimationFrame(runInertia);
  }

  function hasClass(element, className) {
    return (" " + element.className + " ").indexOf(" " + className + " ") >= 0;
  }

  function addClass(element, className) {
    if (!hasClass(element, className)) element.className += " " + className;
  }

  function removeClass(element, className) {
    element.className = (" " + element.className + " ").replace(" " + className + " ", " ").replace(/^\s+|\s+$/g, "");
  }

  function renderPanels() {
    var panels = document.querySelectorAll("[data-panel]");
    var panelIndex;
    var panel;
    var role;
    var swatches;
    var chosen;
    var original;
    var list;
    var i;
    var button;
    var color;
    var selected;

    for (panelIndex = 0; panelIndex < panels.length; panelIndex += 1) {
      panel = panels[panelIndex];
      role = panel.getAttribute("data-panel");
      swatches = panel.querySelector(".swatches");
      chosen = panel.querySelector("[data-chosen]");
      original = panel.querySelector(".original-link");
      list = colors[role];
      swatches.innerHTML = "";

      for (i = 0; i < list.length; i += 1) {
        color = list[i];
        button = document.createElement("button");
        button.className = "swatch";
        button.type = "button";
        button.style.backgroundColor = color.value;
        button.style.setProperty && button.style.setProperty("--swatch", color.value);
        button.setAttribute("aria-label", color.name);
        button.title = color.name;
        button.setAttribute("data-role", role);
        button.setAttribute("data-value", color.value);
        button.onclick = function () {
          state[this.getAttribute("data-role")] = this.getAttribute("data-value");
          clearFrameCache();
          renderedFrame = -1;
          renderPanels();
          draw();
        };
        if (state[role] === color.value) addClass(button, "selected");
        swatches.appendChild(button);
      }

      original.onclick = (function (selectedRole) {
        return function () {
          state[selectedRole] = null;
          clearFrameCache();
          renderedFrame = -1;
          renderPanels();
          draw();
        };
      }(role));

      selected = findColor(role, state[role]);
      chosen.innerHTML = selected ? selected.name : "Origineel";
    }
  }

  function eventClientX(event) {
    if (event.touches && event.touches.length) return event.touches[0].clientX;
    if (event.changedTouches && event.changedTouches.length) return event.changedTouches[0].clientX;
    return event.clientX;
  }

  function startDrag(event) {
    var clientX;
    event = event || window.event;
    if (event.button && event.button !== 0) return;
    if (event.preventDefault) event.preventDefault();
    clientX = eventClientX(event);
    if (typeof clientX !== "number") return;
    stopInertia();
    dragging = true;
    addClass(stage, "dragging");
    dragStartX = clientX;
    dragStartFrame = framePosition;
    lastDragX = clientX;
    lastDragTime = now();
    frameVelocity = 0;
  }

  function moveDrag(event) {
    var clientX;
    var time;
    var elapsed;
    var deltaX;
    var stepX;
    if (!dragging) return;
    event = event || window.event;
    if (event.preventDefault) event.preventDefault();
    clientX = eventClientX(event);
    if (typeof clientX !== "number") return;
    time = now();
    elapsed = Math.max(time - lastDragTime, 1);
    deltaX = clientX - dragStartX;
    stepX = clientX - lastDragX;
    framePosition = normalizedFrame(dragStartFrame - deltaX / PIXELS_PER_FRAME);
    frameVelocity = -(stepX / PIXELS_PER_FRAME) / elapsed;
    lastDragX = clientX;
    lastDragTime = time;
    draw();
  }

  function endDrag() {
    if (!dragging) return;
    dragging = false;
    removeClass(stage, "dragging");
    if (Math.abs(frameVelocity) >= MIN_VELOCITY) {
      stopInertia();
      inertiaFrame = requestAnimationFrame(runInertia);
    }
  }

  function bindDragControls() {
    stage.addEventListener("touchstart", startDrag, false);
    window.addEventListener("touchmove", moveDrag, false);
    window.addEventListener("touchend", endDrag, false);
    window.addEventListener("touchcancel", endDrag, false);
    stage.addEventListener("mousedown", startDrag, false);
    window.addEventListener("mousemove", moveDrag, false);
    window.addEventListener("mouseup", endDrag, false);
  }

  function reset() {
    state.hull = null;
    state.cushions = null;
    state.teak = null;
    clearFrameCache();
    renderedFrame = -1;
    setFrame(0);
    renderPanels();
    draw();
  }

  function downloadImage() {
    var savedPosition = framePosition;
    var link = document.createElement("a");
    setFrame(Math.round(framePosition));
    link.download = "mijn-dammer-360-configuratie.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
    framePosition = savedPosition;
    draw(framePosition, true);
  }

  function normalizeParam(value) {
    return value ? value.replace(/^\s+|\s+$/g, "").toLowerCase().replace(/\s+/g, "") : "";
  }

  function queryParam(name) {
    var pattern = new RegExp("[?&]" + name.replace(/[[]]/g, "\\$&") + "=([^&#]*)");
    var match = pattern.exec(window.location.search);
    return match ? decodeURIComponent(match[1].replace(/\+/g, " ")) : "";
  }

  function applyUrlState() {
    var roles = ["hull", "cushions", "teak"];
    var roleIndex;
    var role;
    var wanted;
    var list;
    var i;
    var match;
    var frame;

    for (roleIndex = 0; roleIndex < roles.length; roleIndex += 1) {
      role = roles[roleIndex];
      wanted = normalizeParam(queryParam(role));
      if (!wanted) continue;
      list = colors[role];
      for (i = 0; i < list.length; i += 1) {
        if (normalizeParam(list[i].name) === wanted || normalizeParam(list[i].value) === wanted) {
          match = list[i];
          break;
        }
      }
      if (match) state[role] = match.value;
      match = null;
    }

    frame = parseInt(queryParam("frame"), 10);
    if (isFinite(frame)) setFrame(frame);
  }

  bindDragControls();
  if (resetButton) resetButton.onclick = reset;
  if (downloadButton) downloadButton.onclick = downloadImage;
  applyUrlState();
  renderPanels();

  loadFrames(function (error) {
    if (error) {
      if (loader) loader.innerHTML = "Renders konden niet worden geladen.";
      return;
    }
    if (loader && loader.parentNode) loader.parentNode.removeChild(loader);
    if (downloadButton) downloadButton.disabled = false;
    draw();
  });
}());
