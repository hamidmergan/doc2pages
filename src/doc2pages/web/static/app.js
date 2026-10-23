"use strict";

// The texts of the page in both languages, the same wording the service uses.
const TEXTS = {
  en: {
    title: "Pages",
    intro: "Your material becomes a learning page with pictures, tables and charts. " +
      "You can look at it, open it in a new tab and download it.",
    filesTitle: "Files",
    dropHere: "Drop your material here",
    formats: "{exts}, at most {max} files",
    removeFile: "Remove",
    tooManySources: "At most {max} sources per page",
    optionsTitle: "Options",
    instructionsLabel: "Instruction, optional",
    instructionsPlaceholder: "For example: only chapter 4, with many examples.",
    imageStyleLabel: "Instruction for pictures",
    imageStylePlaceholder: "For example: watercolour, soft greens.",
    imageStyleHint: "Applies to every picture on the page. Writing in a picture is always ruled out.",
    languageLabel: "Language of the page",
    languageAuto: "From the material",
    translateLabel: "Also in",
    translateOff: "No second language",
    imagesLabel: "Draw the title picture",
    combineLabel: "One page out of all files",
    modelTitle: "Model",
    modelHint: "No model is set in the environment. Enter an OpenAI-compatible endpoint and a model.",
    submit: "Create page",
    creating: "Being created",
    failed: "The page could not be created.",
    resultTitle: "The page",
    openTab: "Open in a new tab",
    download: "Download as ZIP",
    uploadFirst: "Upload material first.",
    step: {
      outline: "Planning the structure",
      section: "Writing the sections",
      sectionCounted: "Writing section {part} of {total}",
      images: "Drawing the pictures",
      imagesCounted: "Drawing picture {part} of {total}",
    },
  },
  de: {
    title: "Pages",
    intro: "Aus deinem Material wird eine Lernseite mit Bildern, Tabellen und Diagrammen. " +
      "Du kannst sie ansehen, in einem neuen Tab öffnen und herunterladen.",
    filesTitle: "Dateien",
    dropHere: "Material hier ablegen",
    formats: "{exts}, höchstens {max} Dateien",
    removeFile: "Entfernen",
    tooManySources: "Höchstens {max} Materialien je Seite",
    optionsTitle: "Einstellungen",
    instructionsLabel: "Anweisung, optional",
    instructionsPlaceholder: "Zum Beispiel: Nur Kapitel 4, mit vielen Beispielen.",
    imageStyleLabel: "Anweisung für Bilder",
    imageStylePlaceholder: "Zum Beispiel: Aquarell, sanfte Grüntöne.",
    imageStyleHint: "Gilt für alle Bilder der Seite. Schrift im Bild wird immer ausgeschlossen.",
    languageLabel: "Sprache der Seite",
    languageAuto: "Aus dem Material",
    translateLabel: "Zusätzlich in",
    translateOff: "Keine zweite Sprache",
    imagesLabel: "Titelbild erzeugen",
    combineLabel: "Eine Seite aus allen Dateien",
    modelTitle: "Modell",
    modelHint: "In der Umgebung ist kein Modell gesetzt. Trag einen OpenAI-kompatiblen Endpunkt und ein Modell ein.",
    submit: "Seite erstellen",
    creating: "Wird erstellt",
    failed: "Die Seite ließ sich nicht erstellen.",
    resultTitle: "Die Seite",
    openTab: "In neuem Tab öffnen",
    download: "Als ZIP herunterladen",
    uploadFirst: "Lade zuerst Material hoch.",
    step: {
      outline: "Der Aufbau wird geplant",
      section: "Die Abschnitte werden geschrieben",
      sectionCounted: "Abschnitt {part} von {total} wird geschrieben",
      images: "Die Bilder werden erzeugt",
      imagesCounted: "Bild {part} von {total} wird erzeugt",
    },
  },
};

const $ = (id) => document.getElementById(id);
const state = { lang: "en", info: null, files: [], pages: [], timer: null };

function fill(text, values) {
  return String(text).replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ""));
}

function t(key, values) {
  const parts = key.split(".");
  let node = TEXTS[state.lang];
  for (const part of parts) node = node && node[part];
  return values ? fill(node || key, values) : (node || key);
}

function paint() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-t]").forEach((el) => {
    el.textContent = t(el.dataset.t);
  });
  $("instructions").placeholder = t("instructionsPlaceholder");
  $("imageStyle").placeholder = t("imageStylePlaceholder");
  if (state.info) {
    $("formats").textContent = t("formats", {
      exts: state.info.extensions.join(", "), max: state.info.max_files,
    });
  }
  document.querySelectorAll(".lang").forEach((b) => {
    b.classList.toggle("on", b.dataset.lang === state.lang);
  });
  paintFiles();
}

function paintFiles() {
  const list = $("chosen");
  list.innerHTML = "";
  state.files.forEach((name) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = name;
    li.appendChild(span);
    list.appendChild(li);
  });
  if (state.files.length) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button";
    button.textContent = t("removeFile");
    button.addEventListener("click", clearFiles);
    li.appendChild(button);
    list.appendChild(li);
  }
}

async function ask(path, options) {
  const answer = await fetch(path, options);
  if (!answer.ok) {
    const body = await answer.text();
    let message = body;
    try {
      message = JSON.parse(body).detail || body;
    } catch (e) { /* a plain text answer */ }
    throw new Error(message || answer.statusText);
  }
  return answer.json();
}

function show(element, text) {
  element.textContent = text || "";
  element.hidden = !text;
}

async function upload(fileList) {
  show($("uploadError"), "");
  const form = new FormData();
  let count = 0;
  for (const file of fileList) {
    form.append("files", file, file.name);
    count += 1;
  }
  if (!count) return;
  try {
    const answer = await ask("/api/upload", { method: "POST", body: form });
    state.files = answer.files;
  } catch (e) {
    show($("uploadError"), e.message);
  }
  paintFiles();
}

async function clearFiles() {
  await ask("/api/clear", { method: "POST" });
  state.files = [];
  paintFiles();
}

function stepText(status) {
  if (status.step === "section" && status.total) {
    return t("step.sectionCounted", { part: Math.min(status.part + 1, status.total), total: status.total });
  }
  if (status.step === "images" && status.total) {
    return t("step.imagesCounted", { part: Math.min(status.part + 1, status.total), total: status.total });
  }
  return t(`step.${status.step}`) !== `step.${status.step}` ? t(`step.${status.step}`) : t("creating");
}

function showPages(pages) {
  state.pages = pages;
  const pick = $("pick");
  pick.innerHTML = "";
  pages.forEach((p) => {
    const option = document.createElement("option");
    option.value = String(p.index);
    option.textContent = p.language ? `${p.title} (${p.language})` : p.title;
    pick.appendChild(option);
  });
  pick.hidden = pages.length < 2;
  $("result").hidden = pages.length === 0;
  if (pages.length) openPage(pages[0].index);
}

function openPage(index) {
  $("view").src = `/api/page/${index}`;
  $("open").href = `/api/page/${index}`;
}

async function poll() {
  let status;
  try {
    status = await ask("/api/status");
  } catch (e) {
    return;
  }
  if (status.state === "running") {
    $("status").textContent = stepText(status);
    return;
  }
  window.clearInterval(state.timer);
  state.timer = null;
  $("submit").disabled = false;
  $("status").textContent = "";
  if (status.state === "error") {
    show($("error"), status.error || t("failed"));
    return;
  }
  if (status.state === "done") showPages(status.pages);
}

async function create() {
  show($("error"), "");
  if (!state.files.length) {
    show($("error"), t("uploadFirst"));
    return;
  }
  const body = {
    instructions: $("instructions").value,
    image_style: $("imageStyle").value,
    language: $("language").value,
    translate_to: $("translateTo").value,
    images: $("images").checked,
    combine: $("combine").checked,
    base_url: $("baseUrl").value,
    model: $("modelName").value,
    api_key: $("apiKey").value,
  };
  $("submit").disabled = true;
  $("result").hidden = true;
  $("status").textContent = t("creating");
  try {
    await ask("/api/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    $("submit").disabled = false;
    $("status").textContent = "";
    show($("error"), e.message);
    return;
  }
  state.timer = window.setInterval(poll, 1500);
}

function wire() {
  document.querySelectorAll(".lang").forEach((button) => {
    button.addEventListener("click", () => {
      state.lang = button.dataset.lang;
      paint();
    });
  });
  const drop = $("drop");
  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("over");
    upload(e.dataTransfer.files);
  });
  $("files").addEventListener("change", (e) => {
    upload(e.target.files);
    e.target.value = "";
  });
  $("submit").addEventListener("click", create);
  $("pick").addEventListener("change", (e) => openPage(Number(e.target.value)));
}

async function start() {
  wire();
  if ((navigator.language || "en").toLowerCase().startsWith("de")) state.lang = "de";
  try {
    state.info = await ask("/api/info");
  } catch (e) {
    state.info = null;
  }
  if (state.info) {
    $("model").textContent = state.info.model || "";
    $("modelCard").hidden = state.info.configured;
    // The environment sets where the fields start, the page can still change them.
    $("language").value = state.info.language || "";
    $("translateTo").value = state.info.translate_to || "";
    $("images").checked = Boolean(state.info.images);
    $("imageStyle").value = state.info.image_style || "";
    $("instructions").value = state.info.instructions || "";
  }
  paint();
}

start();
