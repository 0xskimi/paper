declare const lucide: { createIcons: () => void } | undefined;

import { apiUrl } from './api';
import { initUsdcTip } from './support';
import { haptic } from './haptics';

interface Margins {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

interface JobMeta {
  id: string;
  filename: string;
  basename: string;
  paper: string;
  fontName: string;
  margins: Margins;
  detection: {
    paper: string;
    page_width_mm: number;
    page_height_mm: number;
    margins: Margins;
    header_end_mm: number;
    footer_start_mm: number;
    notes: string[];
  };
  steps: Array<{ id: string; label: string; done: boolean }>;
}

interface JobResponse {
  job: JobMeta;
  urls: {
    previewUrl: string;
    docxUrl: string;
    dotxUrl: string;
  };
}

type Phase = 'upload' | 'processing' | 'review';

const dropzone = document.getElementById('dropzone') as HTMLLabelElement;
const fileInput = document.getElementById('file-input') as HTMLInputElement;
const uploadPanel = document.getElementById('upload-panel') as HTMLDivElement;
const processPanel = document.getElementById('process-panel') as HTMLDivElement;
const reviewPanel = document.getElementById('review-panel') as HTMLDivElement;
const processFilename = document.getElementById('process-filename') as HTMLParagraphElement;
const processSteps = document.getElementById('process-steps') as HTMLUListElement;
const checklist = document.getElementById('checklist') as HTMLUListElement;
const previewOriginal = document.getElementById('preview-original') as HTMLImageElement;
const marginGuide = document.getElementById('margin-guide') as HTMLDivElement;
const errorBanner = document.getElementById('error-banner') as HTMLParagraphElement;
const themeToggle = document.getElementById('theme-toggle') as HTMLButtonElement;

const marginTop = document.getElementById('margin-top') as HTMLInputElement;
const marginBottom = document.getElementById('margin-bottom') as HTMLInputElement;
const marginSide = document.getElementById('margin-side') as HTMLInputElement;
const marginTopOut = document.getElementById('margin-top-out') as HTMLOutputElement;
const marginBottomOut = document.getElementById('margin-bottom-out') as HTMLOutputElement;
const marginSideOut = document.getElementById('margin-side-out') as HTMLOutputElement;
const paperSelect = document.getElementById('paper-select') as HTMLSelectElement;
const fontSelect = document.getElementById('font-select') as HTMLSelectElement;
const rebuildBtn = document.getElementById('rebuild-btn') as HTMLButtonElement;
const resetBtn = document.getElementById('reset-btn') as HTMLButtonElement;
const downloadDotx = document.getElementById('download-dotx') as HTMLAnchorElement;
const downloadDocx = document.getElementById('download-docx') as HTMLAnchorElement;

let current: JobResponse | null = null;
let busy = false;

const PROCESS_LABELS = [
  'Reading your page',
  'Rasterizing artwork at 300 DPI',
  'Finding a safe typing band',
  'Packaging Word letterhead',
];

function refreshIcons() {
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
}

function showError(message: string | null) {
  if (!message) {
    errorBanner.hidden = true;
    errorBanner.textContent = '';
    return;
  }
  errorBanner.hidden = false;
  errorBanner.textContent = message;
}

function setPhase(phase: Phase) {
  uploadPanel.hidden = phase !== 'upload';
  processPanel.hidden = phase !== 'processing';
  reviewPanel.hidden = phase !== 'review';
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function renderProcessSteps(activeIndex: number, doneThrough: number) {
  processSteps.innerHTML = PROCESS_LABELS.map((label, index) => {
    const state = index < doneThrough ? 'is-done' : index === activeIndex ? 'is-active' : '';
    return `<li class="step ${state}"><span class="step-dot"></span><span>${label}</span></li>`;
  }).join('');
}

function updateMarginOutputs() {
  marginTopOut.textContent = `${marginTop.value} mm`;
  marginBottomOut.textContent = `${marginBottom.value} mm`;
  marginSideOut.textContent = `${marginSide.value} mm`;
  updateMarginGuide();
}

function updateMarginGuide() {
  if (!current) return;
  const pageH = current.job.detection.page_height_mm;
  const pageW = current.job.detection.page_width_mm;
  const top = Number(marginTop.value);
  const bottom = Number(marginBottom.value);
  const side = Number(marginSide.value);
  marginGuide.style.top = `${(top / pageH) * 100}%`;
  marginGuide.style.bottom = `${(bottom / pageH) * 100}%`;
  marginGuide.style.left = `${(side / pageW) * 100}%`;
  marginGuide.style.right = `${(side / pageW) * 100}%`;
}

function fillChecklist(job: JobMeta) {
  const items = [
    `Paper · ${job.paper.toUpperCase()} (${job.detection.page_width_mm} × ${job.detection.page_height_mm} mm)`,
    `Top clear · ~${job.detection.header_end_mm} mm from top`,
    `Footer clear · ~${job.detection.footer_start_mm} mm from top`,
    `Typing margins · ${job.margins.top}/${job.margins.bottom}/${job.margins.left}/${job.margins.right} mm`,
    `Body font · ${job.fontName}`,
    ...job.detection.notes,
  ];
  checklist.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join('');
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function applyJob(response: JobResponse) {
  current = response;
  const { job, urls } = response;
  const cacheBust = `?t=${Date.now()}`;
  previewOriginal.src = `${apiUrl(urls.previewUrl)}${cacheBust}`;
  downloadDotx.href = apiUrl(urls.dotxUrl);
  downloadDotx.download = `${job.basename}.dotx`;
  downloadDocx.href = apiUrl(urls.docxUrl);
  downloadDocx.download = `${job.basename}.docx`;

  marginTop.value = String(Math.round(job.margins.top));
  marginBottom.value = String(Math.round(job.margins.bottom));
  const side = Math.round((job.margins.left + job.margins.right) / 2);
  marginSide.value = String(side);
  paperSelect.value = job.paper === 'letter' ? 'letter' : 'a4';
  fontSelect.value = job.fontName || 'Calibri';
  updateMarginOutputs();
  fillChecklist(job);
  setPhase('review');
  refreshIcons();
}

async function createJob(file: File) {
  if (busy) return;
  busy = true;
  showError(null);
  setPhase('processing');
  processFilename.textContent = file.name;
  renderProcessSteps(0, 0);
  haptic('nudge');

  const form = new FormData();
  form.append('file', file);

  let step = 0;
  const tick = window.setInterval(() => {
    step = Math.min(step + 1, PROCESS_LABELS.length - 1);
    renderProcessSteps(step, step);
  }, 450);

  try {
    // Let the staged UI paint before the request returns.
    await sleep(120);
    const res = await fetch(apiUrl('/api/jobs'), { method: 'POST', body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || 'Could not process that file.');
    }
    window.clearInterval(tick);
    renderProcessSteps(PROCESS_LABELS.length - 1, PROCESS_LABELS.length);
    await sleep(280);
    applyJob(data as JobResponse);
    haptic('success');
  } catch (error) {
    window.clearInterval(tick);
    setPhase('upload');
    const message = error instanceof Error ? error.message : 'Something went wrong.';
    showError(message);
    haptic('error');
  } finally {
    busy = false;
    fileInput.value = '';
  }
}

async function rebuild() {
  if (!current || busy) return;
  busy = true;
  rebuildBtn.disabled = true;
  rebuildBtn.textContent = 'Applying…';
  showError(null);

  const side = Number(marginSide.value);
  const payload = {
    paper: paperSelect.value,
    font_name: fontSelect.value,
    margins: {
      top: Number(marginTop.value),
      bottom: Number(marginBottom.value),
      left: side,
      right: side,
    },
  };

  try {
    const res = await fetch(apiUrl(`/api/jobs/${current.job.id}/rebuild`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || 'Could not rebuild template.');
    }
    applyJob(data as JobResponse);
    haptic('success');
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Something went wrong.';
    showError(message);
    haptic('error');
  } finally {
    busy = false;
    rebuildBtn.disabled = false;
    rebuildBtn.textContent = 'Apply adjustments';
  }
}

function reset() {
  current = null;
  showError(null);
  setPhase('upload');
  haptic('light');
}

function handleFiles(files: FileList | null) {
  const file = files?.[0];
  if (!file) return;
  const okType =
    file.type === 'application/pdf' ||
    file.type.startsWith('image/') ||
    /\.(pdf|png|jpe?g|webp)$/i.test(file.name);
  if (!okType) {
    showError('Use a PDF or image letterhead.');
    haptic('error');
    return;
  }
  if (file.size > 25 * 1024 * 1024) {
    showError('That file is too big. Try one under 25MB.');
    haptic('error');
    return;
  }
  void createJob(file);
}

function initTheme() {
  const root = document.documentElement;
  themeToggle.addEventListener('click', () => {
    haptic('selection');
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('paper-theme', next);
    refreshIcons();
  });
}

initTheme();
initUsdcTip();
refreshIcons();
setPhase('upload');
updateMarginOutputs();

for (const input of [marginTop, marginBottom, marginSide]) {
  input.addEventListener('input', () => {
    updateMarginOutputs();
  });
}

rebuildBtn.addEventListener('click', () => {
  void rebuild();
});
resetBtn.addEventListener('click', reset);

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  if (!dropzone.classList.contains('is-dragover')) haptic('selection');
  dropzone.classList.add('is-dragover');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('is-dragover');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('is-dragover');
  handleFiles(e.dataTransfer?.files ?? null);
});

fileInput.addEventListener('change', () => handleFiles(fileInput.files));
