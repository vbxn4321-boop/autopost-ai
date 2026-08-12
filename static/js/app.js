/* ───────────────────────────────────────────────────────
   상태 관리 (타임라인 기반 — 이미지 기본 2초 / 영상 기본 4초)
─────────────────────────────────────────────────────── */
const state = {
  platform: 'instagram',
  timeline: [],              // [{path, type: 'image'|'video', duration, name}]
  originalContent: '',
  generatedData: null,
  selectedBGM: 'none',       // 'none' | 'custom'
  customBgmPath: null,
  bgmVolume: 0.3,
};

/* 서버가 메모리 부족 등으로 재시작되면 응답이 중간에 끊겨 res.json()이 그대로
   "Unexpected end of JSON input" 같은 기술적 에러를 던진다 — 사용자에게는
   이해할 수 있는 문구로 바꿔서 보여준다. */
async function parseJsonResponse(res) {
  const text = await res.text();
  if (!text) {
    throw new Error('서버가 응답하지 않았어요. 서버가 잠시 재시작 중일 수 있어요 — 잠시 후 다시 시도해주세요.');
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error('서버 응답을 처리하지 못했어요. 잠시 후 다시 시도해주세요.');
  }
}

const PLATFORM_NAMES = {
  instagram:  '인스타그램',
  tiktok:     '틱톡',
  naver_blog: '블로그',
  facebook:   '페이스북',
  x_twitter:  'X (트위터)',
  threads:    '스레드',
};

const PLATFORM_CHAR_LIMITS = {
  instagram:  2200,
  tiktok:     2200,
  naver_blog: 10000,
  facebook:   63206,
  x_twitter:  280,
  threads:    500,
};

/* ───────────────────────────────────────────────────────
   초기화
─────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const today = new Date();
  document.getElementById('scheduleDate').value = today.toISOString().split('T')[0];
  document.getElementById('scheduleTime').value = '09:00';

  document.getElementById('editorArea').addEventListener('input', updateCharCounter);

  document.getElementById('bgmVolume').addEventListener('input', (e) => {
    state.bgmVolume = e.target.value / 100;
    document.getElementById('bgmVolumeLabel').textContent = `${e.target.value}%`;
  });

  document.getElementById('fileInput').addEventListener('change', handleFileSelect);
  document.getElementById('bgmFileInput').addEventListener('change', handleBgmFileSelect);

  const dz = document.getElementById('dropzone');
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.classList.remove('dragover');
    Array.from(e.dataTransfer.files).forEach(handleFile);
  });

  document.querySelectorAll('.faq-question').forEach(item => {
    item.addEventListener('click', () => {
      const parent = item.parentElement;
      const isActive = parent.classList.contains('active');
      document.querySelectorAll('.faq-item').forEach(faq => {
        faq.classList.remove('active');
        faq.querySelector('span').textContent = '▼';
      });
      if (!isActive) {
        parent.classList.add('active');
        item.querySelector('span').textContent = '▲';
      }
    });
  });

  renderTimeline();
  loadScheduledPosts();
  loadConnectionStatus();
  updateCharCounter();
  syncThemeToggleIcon();
  // 마법사 스텝은 시작 화면(wizardIntro)에서 "시작하기"를 눌러야 진입함 — startWizard() 참고
});

/* ───────────────────────────────────────────────────────
   플랫폼 선택 (좌측 사이드바)
─────────────────────────────────────────────────────── */
document.getElementById('platformTabs').addEventListener('click', (e) => {
  const tab = e.target.closest('.platform-tab-row');
  if (!tab) return;

  document.querySelectorAll('.platform-tab-row').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');

  state.platform = tab.dataset.platform;
  document.getElementById('platformBadge').textContent = PLATFORM_NAMES[state.platform];
  updateCharCounter();

  // 플랫폼은 한 번 고르면 바로 다음 질문으로 — 마법사 흐름의 핵심
  setTimeout(() => nextStep(), 250);
});

/* ───────────────────────────────────────────────────────
   타임라인 에디터: 파일 업로드 → 클립 추가
─────────────────────────────────────────────────────── */
function handleFileSelect(e) {
  Array.from(e.target.files).forEach(handleFile);
  e.target.value = '';
}

function handleFile(file) {
  const isVideo = file.type.startsWith('video/');
  const isImage = file.type.startsWith('image/');

  if (!isVideo && !isImage) {
    showToast('지원하지 않는 파일 형식입니다', 'error');
    return;
  }

  if (isVideo) document.getElementById('sttOption').style.display = 'block';

  uploadFile(file, isVideo ? 'video' : 'image');
}

async function uploadFile(file, type) {
  const progressWrap = document.getElementById('uploadProgress');
  const progressFill = document.getElementById('uploadProgressFill');
  const progressLabel = document.getElementById('uploadProgressLabel');

  progressWrap.classList.add('visible');
  progressFill.style.background = '';
  progressFill.style.width = '30%';
  progressLabel.textContent = `${file.name} 업로드 중...`;

  try {
    const formData = new FormData();
    formData.append('video', file);

    const runSTT = type === 'video' && document.getElementById('runSTT').checked;
    formData.append('run_stt', runSTT.toString());

    progressFill.style.width = '60%';
    if (runSTT) progressLabel.textContent = 'Whisper STT 실행 중 (시간이 걸릴 수 있습니다)...';

    const res = await fetch('/api/upload-video', { method: 'POST', body: formData });
    const data = await parseJsonResponse(res);

    if (!data.success) throw new Error(data.error || '업로드 실패');

    progressFill.style.width = '100%';
    progressLabel.textContent = '✅ 업로드 완료!';

    addClipToTimeline(data.file_path, type, file.name);
    showToast(`"${file.name}" 타임라인에 추가됨`, 'success');

    if (data.transcript) {
      document.getElementById('topicInput').value = data.transcript;
      showToast('🎙️ 음성 텍스트 추출 완료', 'info');
    }

    setTimeout(() => progressWrap.classList.remove('visible'), 1500);
  } catch (err) {
    progressLabel.textContent = `❌ ${err.message}`;
    progressFill.style.width = '100%';
    progressFill.style.background = '#ef4444';
    showToast(err.message, 'error');
  }
}

/* ───────────────────────────────────────────────────────
   타임라인 클립 관리 (이미지 기본 2초 / 영상 기본 4초)
─────────────────────────────────────────────────────── */
function addClipToTimeline(path, type, name) {
  state.timeline.push({ path, type, duration: type === 'video' ? 4 : 2, name: name || '' });
  renderTimeline();
}

function removeClip(index) {
  state.timeline.splice(index, 1);
  renderTimeline();
}

function moveClip(index, dir) {
  const target = index + dir;
  if (target < 0 || target >= state.timeline.length) return;
  const tmp = state.timeline[index];
  state.timeline[index] = state.timeline[target];
  state.timeline[target] = tmp;
  renderTimeline();
}

function updateClipDuration(index, value) {
  const d = parseFloat(value);
  if (!isNaN(d) && d > 0) state.timeline[index].duration = d;
}

function renderTimeline() {
  const strip = document.getElementById('timelineStrip');
  updateMediaAnalysisButtons();

  if (!state.timeline.length) {
    strip.innerHTML = '<div class="timeline-empty">아직 추가된 미디어가 없습니다 — 위에서 사진/영상을 올리거나 "주제로 이미지 자동생성"을 눌러보세요.</div>';
    return;
  }

  strip.innerHTML = state.timeline.map((clip, i) => {
    const filename = clip.path.split(/[\\/]/).pop();
    const thumb = clip.type === 'video'
      ? `<div class="timeline-clip-thumb" style="display:flex;align-items:center;justify-content:center;font-size:26px;">🎬</div>`
      : `<img class="timeline-clip-thumb" src="/uploads/${filename}" alt="clip" onerror="this.src='/outputs/${filename}'" />`;

    return `
      <div class="timeline-clip">
        <span class="timeline-clip-type">${clip.type === 'video' ? '🎬' : '🖼'}</span>
        <button class="timeline-clip-remove" onclick="removeClip(${i})" title="삭제">✕</button>
        ${thumb}
        <div class="timeline-clip-controls">
          <button onclick="moveClip(${i}, -1)" title="앞으로 이동">◀</button>
          <input class="timeline-clip-duration" type="number" min="0.5" step="0.5" value="${clip.duration}"
                 onchange="updateClipDuration(${i}, this.value)" title="재생 시간(초)" />
          <button onclick="moveClip(${i}, 1)" title="뒤로 이동">▶</button>
        </div>
      </div>
    `;
  }).join('');
}

/* 타임라인에 해당 종류(영상/사진)의 클립이 없으면 관련 분석 버튼을 미리 비활성화해서
   "타임라인에 영상/사진이 있어야 해요" 오류를 아예 안 만나게 한다 */
function updateMediaAnalysisButtons() {
  const hasVideo = state.timeline.some(c => c.type === 'video');
  const hasImage = state.timeline.some(c => c.type === 'image');

  const styleBtn = document.getElementById('analyzeStyleBtn');
  if (styleBtn) {
    styleBtn.disabled = !hasVideo;
    styleBtn.title = hasVideo ? '' : '타임라인에 영상이 있어야 사용할 수 있어요';
  }

  const photoBtn = document.getElementById('analyzePhotoBtn');
  if (photoBtn) {
    photoBtn.disabled = !hasImage;
    photoBtn.title = hasImage ? '' : '타임라인에 사진이 있어야 사용할 수 있어요';
  }
}

/* ───────────────────────────────────────────────────────
   주제만으로 이미지 자동 생성 (Pollinations.ai, 비용 0원)
─────────────────────────────────────────────────────── */
async function generateImageFromTopic() {
  const topic = document.getElementById('topicInput').value.trim();
  if (!topic) {
    showToast('먼저 아래에서 주제를 입력해주세요', 'error');
    document.getElementById('topicInput').focus();
    return;
  }

  const btn = document.getElementById('imageGenBtn');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>이미지 생성 중...';

  try {
    const res = await fetch('/api/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic,
        platform: state.platform,
        business_type: document.getElementById('businessType').value,
        tone: document.getElementById('toneInput').value,
      }),
    });
    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || '이미지 생성 실패');

    addClipToTimeline(data.data.image_path, 'image', '자동생성 이미지');
    showToast('🪄 이미지가 자동 생성되어 타임라인에 추가됐어요!', 'success');
  } catch (err) {
    showToast(`이미지 생성 실패: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

/* ───────────────────────────────────────────────────────
   영상 진행 중 프레임 몇 장만 캡처해 스타일(자막 위치/색상) 자동분석
─────────────────────────────────────────────────────── */
async function analyzeVideoStyle() {
  const videoClip = state.timeline.find(c => c.type === 'video');
  if (!videoClip) {
    showToast('타임라인에 영상이 있어야 스타일을 분석할 수 있어요', 'error');
    return;
  }

  const btn = document.getElementById('analyzeStyleBtn');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>프레임 분석 중...';

  try {
    const res = await fetch('/api/analyze-style', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: videoClip.path }),
    });
    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || '분석 실패');

    const style = data.data;
    if (style.subtitle_position) document.getElementById('subtitlePosition').value = style.subtitle_position;
    if (style.subtitle_color) document.getElementById('subtitleColor').value = toHexColor(style.subtitle_color);
    showToast(`🔍 자막 스타일 자동 추천 완료 — ${style.reasoning || ''}`, 'success');
  } catch (err) {
    showToast(`스타일 분석 실패: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

function toHexColor(name) {
  // 이미 #RRGGBB 형식이면 그대로, 색상 이름(white 등)이면 <input type=color>가 못 읽으므로 임시 캔버스로 변환
  if (/^#[0-9a-fA-F]{6}$/.test(name)) return name;
  const ctx = document.createElement('canvas').getContext('2d');
  ctx.fillStyle = name;
  return ctx.fillStyle.startsWith('#') ? ctx.fillStyle : '#ffffff';
}

/* ───────────────────────────────────────────────────────
   사진 자동 분석 (Gemini Vision) — 사진 설명을 직접 안 써도 되게 해줌
─────────────────────────────────────────────────────── */
async function analyzePhoto() {
  const imageClip = state.timeline.find(c => c.type === 'image');
  if (!imageClip) {
    showToast('타임라인에 사진이 있어야 자동 분석할 수 있어요', 'error');
    return;
  }

  const btn = document.getElementById('analyzePhotoBtn');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>분석 중...';

  try {
    const res = await fetch('/api/analyze-photo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_path: imageClip.path }),
    });
    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || '분석 실패');

    document.getElementById('photoDesc').value = data.data.description;
    showToast('🔍 사진 분석 완료! 설명이 자동으로 채워졌어요', 'success');
  } catch (err) {
    showToast(`사진 분석 실패: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

/* ───────────────────────────────────────────────────────
   스타일 클론(더미) — 실제 URL을 서버가 가져오지 않고, 준비된 프리셋 중 하나를 추천
─────────────────────────────────────────────────────── */
async function applyStyleClone() {
  const url = document.getElementById('styleCloneUrl').value.trim();
  if (!url) { showToast('참고할 URL을 입력해주세요', 'error'); return; }

  const btn = document.getElementById('styleCloneBtn');
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>불러오는 중...';

  try {
    const res = await fetch('/api/style-clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_url: url }),
    });
    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || '스타일 클론 실패');

    const style = data.data;
    document.getElementById('subtitleColor').value = style.subtitle_color;
    document.getElementById('subtitleBg').value = style.subtitle_bg === 'transparent' ? '#000000' : style.subtitle_bg;
    document.getElementById('subtitleBgEnabled').checked = style.subtitle_bg !== 'transparent';
    document.getElementById('subtitlePosition').value = style.subtitle_position;

    const toneSelect = document.getElementById('toneInput');
    for (const opt of toneSelect.options) {
      if (opt.value === style.tone) { toneSelect.value = style.tone; break; }
    }

    const resultEl = document.getElementById('styleCloneResult');
    resultEl.classList.add('visible');
    resultEl.textContent = `✨ "${style.name}" 스타일 적용됨 — ${style.note}`;

    showToast(`🎨 "${style.name}" 스타일이 적용됐어요`, 'success');
  } catch (err) {
    showToast(`스타일 클론 실패: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

/* ───────────────────────────────────────────────────────
   BGM 선택 / 업로드
─────────────────────────────────────────────────────── */
function selectBGM(el, bgmKey) {
  if (el.classList.contains('disabled')) return;
  document.querySelectorAll('.bgm-item').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  state.selectedBGM = bgmKey;
}

async function handleBgmFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;

  try {
    const formData = new FormData();
    formData.append('bgm', file);
    const res = await fetch('/api/upload-bgm', { method: 'POST', body: formData });
    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || 'BGM 업로드 실패');

    state.customBgmPath = data.file_path;
    state.selectedBGM = 'custom';
    document.querySelectorAll('.bgm-item').forEach(b => b.classList.remove('selected'));
    showToast(`🎵 "${file.name}" BGM으로 설정됨`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ───────────────────────────────────────────────────────
   AI 원고 생성 + 앵커 애니메이션("데이터만 넣으면 됩니다")
─────────────────────────────────────────────────────── */
async function generateContent() {
  const topic = document.getElementById('topicInput').value.trim();
  const photoDesc = document.getElementById('photoDesc').value.trim();

  if (!topic && !photoDesc) {
    showToast('주제 또는 사진 설명을 입력해주세요', 'error');
    document.getElementById('topicInput').focus();
    return;
  }

  const fullTopic = topic + (photoDesc ? ` / 이미지: ${photoDesc}` : '');

  // generateBtn은 마법사 UI에서 더 이상 존재하지 않을 수 있음(자동 트리거로 대체됨) — 있으면만 갱신
  const btn = document.getElementById('generateBtn');
  if (btn) {
    btn.classList.add('loading');
    btn.innerHTML = '<span class="spinner"></span>AI 생성 중...';
  }

  const editor = document.getElementById('editorArea');
  editor.classList.add('typing-effect');
  editor.value = '';

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: fullTopic,
        platform: state.platform,
        business_type: document.getElementById('businessType').value,
        location: document.getElementById('locationInput').value,
        tone: document.getElementById('toneInput').value,
      }),
    });

    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || '생성 실패');

    const result = data.data;
    state.originalContent = result.full_post || result.caption || result.body || '';
    state.generatedData = result;

    await typeText(editor, state.originalContent);
    editor.classList.remove('typing-effect');

    if (result.hashtags && result.hashtags.length > 0) showHashtags(result.hashtags);

    document.getElementById('restoreBtn').disabled = false;
    document.getElementById('regenBtn').disabled = false;

    updateCharCounter();
    showToast('✨ 원고 생성 완료!', 'success');

  } catch (err) {
    editor.classList.remove('typing-effect');
    if (err.message === 'LIMIT_EXCEEDED') {
      editor.value = '';
      showUpgradeModal();
    } else {
      editor.value = `[오류] ${err.message}\n\n.env 파일에 GEMINI_API_KEY를 설정했는지 확인해주세요.`;
      showToast(err.message, 'error');
    }
  } finally {
    if (btn) {
      btn.classList.remove('loading');
      btn.innerHTML = '✨ AI 원고 자동 생성';
    }
  }
}

/* ───────────────────────────────────────────────────────
   타임라인 합성 (이미지 2초/영상 4초 기본 배치 + 자막/BGM)
─────────────────────────────────────────────────────── */
async function composeTimeline() {
  if (!state.timeline.length) {
    showToast('먼저 타임라인에 사진/영상을 추가해주세요', 'error');
    return;
  }

  const btn = document.getElementById('composeBtn');
  btn.classList.add('loading');
  btn.innerHTML = '<span class="spinner"></span>영상 합성 중... (최대 1~2분 소요)';

  const subtitle_options = {
    font: document.getElementById('subtitleFont').value,
    position: document.getElementById('subtitlePosition').value === 'top' ? ['center', 0.1] :
              document.getElementById('subtitlePosition').value === 'bottom' ? ['center', 0.85] :
              ['center', 0.5],
    color: document.getElementById('subtitleColor').value,
    bg_color: document.getElementById('subtitleBgEnabled').checked ? document.getElementById('subtitleBg').value : 'transparent',
    stroke_color: '#000000',
    stroke_width: document.getElementById('subtitleOutline').checked ? 2 : 0,
  };

  const bgmPath = state.selectedBGM === 'custom' ? state.customBgmPath : null;

  try {
    const res = await fetch('/api/compose-timeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clips: state.timeline.map(c => ({ path: c.path, type: c.type, duration: c.duration })),
        platform: state.platform,
        subtitle_text: document.getElementById('editorArea').value.trim(),
        subtitle_options,
        bgm_path: bgmPath,
      }),
    });

    const data = await parseJsonResponse(res);
    if (!data.success) throw new Error(data.error || '합성 실패');

    const output_path = data.data.output_path;
    const filename = output_path.split(/[\\/]/).pop();

    showToast('✨ 영상 합성 완료! 다운로드를 시작합니다.', 'success');

    const a = document.createElement('a');
    a.href = `/api/download/${filename}`;
    a.download = filename;
    a.click();

  } catch (err) {
    showToast(`합성 오류: ${err.message}`, 'error');
  } finally {
    btn.classList.remove('loading');
    btn.innerHTML = '🎬 완성 영상 만들기';
  }
}

/* 타이핑 효과 */
async function typeText(element, text) {
  element.value = '';
  const delay = Math.max(5, Math.min(20, 1500 / text.length));
  for (let i = 0; i < text.length; i++) {
    element.value += text[i];
    element.scrollTop = element.scrollHeight;
    if (i % 5 === 0) await new Promise(r => setTimeout(r, delay));
  }
}

/* 재생성 */
async function regenerateContent() { await generateContent(); }

/* 원문 복구 */
function restoreOriginal() {
  if (!state.originalContent) return;
  document.getElementById('editorArea').value = state.originalContent;
  updateCharCounter();
  showToast('원문이 복구되었습니다', 'info');
}

/* 클립보드 복사 */
function copyToClipboard() {
  const text = document.getElementById('editorArea').value;
  if (!text.trim()) { showToast('복사할 내용이 없습니다', 'error'); return; }
  navigator.clipboard.writeText(text).then(() => showToast('📋 클립보드에 복사됨', 'success'));
}

/* 텍스트 파일 다운로드 */
function downloadText() {
  const text = document.getElementById('editorArea').value;
  if (!text.trim()) { showToast('다운로드할 원고가 없습니다', 'error'); return; }
  const platform = PLATFORM_NAMES[state.platform] || 'SNS';
  const now = new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
  const filename = `${platform}_원고_${now}.txt`;
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
  showToast('⬇️ 원고 TXT 파일 다운로드 완료!', 'success');
}

/* 해시태그 복사 */
function copyHashtags() {
  const chips = document.querySelectorAll('.hashtag-chip');
  const tags = Array.from(chips).map(c => c.textContent).join(' ');
  navigator.clipboard.writeText(tags).then(() => showToast('🏷️ 해시태그 복사됨', 'success'));
}

/* ───────────────────────────────────────────────────────
   해시태그 표시
─────────────────────────────────────────────────────── */
function showHashtags(hashtags) {
  const area = document.getElementById('hashtagArea');
  const list = document.getElementById('hashtagList');
  area.style.display = 'block';
  list.innerHTML = hashtags.map(tag => `
    <span class="hashtag-chip" onclick="addHashtagToEditor('${tag}', this)">${tag}</span>
  `).join('');
}

function addHashtagToEditor(tag, chipEl) {
  const editor = document.getElementById('editorArea');
  const current = editor.value;

  if (chipEl.classList.contains('selected')) {
    chipEl.classList.remove('selected');
    const lines = current.split('\n').filter(line => line.trim() !== tag.trim());
    editor.value = lines.join('\n');
  } else {
    chipEl.classList.add('selected');
    if (!current.includes(tag)) {
      editor.value = current + (current.endsWith('\n') ? '' : '\n') + tag;
    }
  }
  updateCharCounter();
}

function resetHashtags() {
  document.querySelectorAll('.hashtag-chip.selected').forEach(chip => chip.classList.remove('selected'));
  showToast('해시태그 선택이 초기화되었습니다', 'info');
}

/* ───────────────────────────────────────────────────────
   글자수 카운터
─────────────────────────────────────────────────────── */
function updateCharCounter() {
  const text = document.getElementById('editorArea').value;
  const count = text.length;
  const limit = PLATFORM_CHAR_LIMITS[state.platform] || 2200;
  const counter = document.getElementById('charCounter');
  const countEl = document.getElementById('charCount');
  const limitEl = document.getElementById('charLimit');

  countEl.textContent = count.toLocaleString();
  limitEl.textContent = `/ ${limit.toLocaleString()}자`;

  counter.className = 'char-counter';
  if (count > limit * 0.9) counter.classList.add('danger');
  else if (count > limit * 0.7) counter.classList.add('warning');
}

/* ───────────────────────────────────────────────────────
   예약 발행
─────────────────────────────────────────────────────── */
async function schedulePost() {
  const content = document.getElementById('editorArea').value.trim();
  const date = document.getElementById('scheduleDate').value;
  const time = document.getElementById('scheduleTime').value;

  if (!content) { showToast('발행할 원고를 먼저 작성해주세요', 'error'); return; }
  if (!date || !time) { showToast('날짜와 시간을 선택해주세요', 'error'); return; }

  const hashtags = Array.from(document.querySelectorAll('.hashtag-chip')).map(c => c.textContent);
  const timelineForSchedule = state.timeline.map(c => ({ path: c.path, type: c.type, duration: c.duration }));

  try {
    const res = await fetch('/api/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: state.platform,
        content,
        caption: content,
        hashtags,
        media_path: state.timeline[0]?.path || null,
        timeline: timelineForSchedule.length ? timelineForSchedule : null,
        scheduled_at: `${date} ${time}`,
      }),
    });

    const data = await parseJsonResponse(res);
    if (data.success) {
      showToast(`📅 ${PLATFORM_NAMES[state.platform]} 게시물 예약 완료! (ID: ${data.post_id})`, 'success');
      loadScheduledPosts();
    } else {
      throw new Error(data.error);
    }
    return data;
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ───────────────────────────────────────────────────────
   예약 취소(삭제)
─────────────────────────────────────────────────────── */
async function deleteScheduledPost(postId) {
  if (!confirm('이 예약 게시물을 취소하시겠습니까?')) return;
  try {
    const res = await fetch(`/api/schedule/${postId}`, { method: 'DELETE' });
    const data = await parseJsonResponse(res);
    if (data.success) {
      const el = document.getElementById(`schedule-item-${postId}`);
      if (el) {
        el.style.transition = 'all 0.3s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateX(20px)';
        setTimeout(() => el.remove(), 300);
      }
      showToast('예약이 취소되었습니다', 'info');
    } else {
      throw new Error(data.error || '삭제 실패');
    }
  } catch (err) {
    const el = document.getElementById(`schedule-item-${postId}`);
    if (el) { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }
    showToast('예약 항목을 삭제했습니다', 'info');
  }
}

/* ───────────────────────────────────────────────────────
   예약 목록 로드
─────────────────────────────────────────────────────── */
async function loadScheduledPosts() {
  try {
    const res = await fetch('/api/scheduled-posts');
    const data = await parseJsonResponse(res);
    renderScheduleList(data.data || []);
  } catch (err) {
    // 서버 미실행 시 무시
  }
}

function renderScheduleList(posts) {
  const list = document.getElementById('scheduleList');
  if (!posts.length) {
    list.innerHTML = '<div class="empty-state"><span class="empty-icon">📅</span>예약된 게시물이 없습니다</div>';
    return;
  }

  const PLATFORM_ICONS = { instagram: '📸', tiktok: '🎵', naver_blog: '📝', facebook: '📘', x_twitter: '🐦', threads: '🧵' };
  const STATUS_CLASS = { pending: 'status-pending', published: 'status-published', failed: 'status-failed' };
  const STATUS_TEXT  = { pending: '대기 중', published: '발행 완료', failed: '실패' };

  list.innerHTML = posts.slice(0, 10).map(p => {
    let statusText = STATUS_TEXT[p.status] || p.status;
    if (p.status === 'failed' && typeof p.retry_count === 'number') {
      statusText = p.retry_count >= 3 ? '실패 (재시도 소진)' : `실패 (재시도 ${p.retry_count}/3)`;
    }
    return `
    <div class="schedule-item" id="schedule-item-${p.id}">
      <span>${PLATFORM_ICONS[p.platform] || '📄'}</span>
      <span style="flex:1; color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
        ${(p.content || '').substring(0, 30)}...
      </span>
      <span style="color:var(--text-muted); font-size:10px;">${(p.scheduled_at || '').substring(0, 16)}</span>
      <span class="schedule-status ${STATUS_CLASS[p.status] || ''}">${statusText}</span>
      ${p.status === 'pending' || p.status === 'failed' ? `<button class="btn-delete-schedule" onclick="deleteScheduledPost(${p.id})" title="예약 취소">✕ 취소</button>` : ''}
    </div>
  `;
  }).join('');
}

/* ───────────────────────────────────────────────────────
   SNS 연결 상태 (좌측 사이드바 표시용)
─────────────────────────────────────────────────────── */
async function loadConnectionStatus() {
  try {
    const res = await fetch('/api/connection-status');
    const data = await parseJsonResponse(res);
    if (!data.success) return;
    Object.entries(data.data).forEach(([platform, connected]) => {
      const dot = document.getElementById(`conn-${platform}`);
      if (dot) dot.textContent = connected ? '🟢' : '🔴';
    });
  } catch (err) {
    // 무시
  }
}

/* ───────────────────────────────────────────────────────
   즉시 발행 / 클립보드 복사 후 이동
─────────────────────────────────────────────────────── */
async function publishNow(platform) {
  const content = document.getElementById('editorArea').value.trim();
  if (!content) {
    showToast('발행할 원고가 없습니다. 먼저 AI 원고를 생성해주세요!', 'error');
    return;
  }

  const platformName = PLATFORM_NAMES[platform] || platform;

  const unavailable = ['threads'];
  if (unavailable.includes(platform)) {
    showToast(`${platformName}은(는) 현재 메타 개발자 인증 대기 중입니다. 곧 활성화됩니다!`, 'info');
    return;
  }

  if (!confirm(`${platformName}에 즉시 발행하시겠습니까?`)) return;

  showToast(`🚀 ${platformName}(으)로 발행 중...`, 'info');

  try {
    const resp = await fetch('/api/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform,
        title: state.generatedData?.title || '',
        content,
        caption: state.generatedData?.caption || '',
        hashtags: state.generatedData?.hashtags || '',
        media_path: state.timeline[0]?.path || '',
      }),
    });

    const result = await parseJsonResponse(resp);

    if (result.success) {
      if (result.data?.manual_required && result.data?.write_url) {
        const textToCopy = result.data.prepared_content || content;
        navigator.clipboard.writeText(textToCopy).then(() => {
          showToast('📋 원고가 클립보드에 복사됐습니다. 새 창에 붙여넣기 해주세요!', 'success');
        });
        window.open(result.data.write_url, '_blank');
      } else {
        const url = result.data?.url || '';
        showToast(`🎉 ${platformName} 발행 성공!${url ? ' ' + url : ''}`, 'success');
      }
      if (result.data?.note) {
        setTimeout(() => showToast(`📌 ${result.data.note}`, 'info'), 2000);
      }
    } else {
      showToast(`❌ ${platformName} 발행 실패: ${result.data?.error || result.error || '알 수 없는 오류'}`, 'error');
    }
    return result;
  } catch (err) {
    showToast(`❌ 네트워크 오류: ${err.message}`, 'error');
  }
}

function copyAndAlert(platform) {
  copyToClipboard();
  showToast(`📋 원고가 복사되었습니다. ${PLATFORM_NAMES[platform]} 앱을 열어 붙여넣기 해주세요!`, 'success');
}

/* ───────────────────────────────────────────────────────
   프리셋 퀵버튼 (업종별 빠른 주제 채우기)
─────────────────────────────────────────────────────── */
function applyPreset(text, el) {
  document.getElementById('topicInput').value = text;
  document.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));
  if (el) {
    el.classList.add('active');
    setTimeout(() => el.classList.remove('active'), 1500);
  }
  onTopicInput();
  document.getElementById('topicInput').focus();
}

/* ───────────────────────────────────────────────────────
   토스트 알림
─────────────────────────────────────────────────────── */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const icons = { success: '✅', error: '❌', info: '💡' };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || '💡'}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ───────────────────────────────────────────────────────
   업그레이드 모달
─────────────────────────────────────────────────────── */
function showUpgradeModal(e) {
  if (e) e.preventDefault();
  document.getElementById('upgradeModal').classList.add('active');
}
function hideUpgradeModal() {
  document.getElementById('upgradeModal').classList.remove('active');
}

/* ───────────────────────────────────────────────────────
   마법사(Wizard) 스텝 네비게이션 — 토스 스타일 "1화면 1질문"
─────────────────────────────────────────────────────── */
let currentStep = 1;
let hasAutoGenerated = false;
const TOTAL_STEPS = 5;

function goToWizardStep(n) {
  document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
  const target = document.querySelector(`.wizard-step[data-step="${n}"]`);
  if (target) target.classList.add('active');
  currentStep = n;

  document.querySelectorAll('.wizard-progress-dots .dot').forEach((dot, i) => {
    const stepNum = i + 1;
    dot.classList.remove('done', 'current');
    if (stepNum < n) dot.classList.add('done');
    else if (stepNum === n) dot.classList.add('current');
  });

  document.getElementById('wizardBackBtn').disabled = (n === 1);

  const nav = document.getElementById('wizardNav');
  if (n === 1 || n === 5) {
    nav.style.display = 'none';
  } else {
    nav.style.display = 'block';
    updateNextButton();
  }

  if (n === 4) {
    autoGenerateIfNeeded();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function nextStep() {
  if (currentStep < TOTAL_STEPS) goToWizardStep(currentStep + 1);
}

function prevStep() {
  if (currentStep > 1) goToWizardStep(currentStep - 1);
}

function updateNextButton() {
  const btn = document.getElementById('wizardNextBtn');
  btn.textContent = '다음 →';
  if (currentStep === 2) {
    btn.disabled = !document.getElementById('topicInput').value.trim();
  } else if (currentStep === 4) {
    btn.disabled = !document.getElementById('editorArea').value.trim();
  } else {
    btn.disabled = false;
  }
}

/* 시작화면과 각 스텝이 같은 하단 버튼을 공유 — 지금 보이는 화면에 맞는 동작으로 분기 */
function handleWizardNavClick() {
  if (document.getElementById('wizardIntro').classList.contains('active')) {
    startWizard();
  } else {
    nextStep();
  }
}

function onTopicInput() {
  if (currentStep === 2) updateNextButton();
}

async function autoGenerateIfNeeded() {
  if (hasAutoGenerated && document.getElementById('editorArea').value.trim()) {
    updateNextButton();
    return;
  }
  document.getElementById('wizardGenLoading').style.display = 'flex';
  document.getElementById('step4Content').style.display = 'none';

  await generateContent();

  hasAutoGenerated = true;
  document.getElementById('wizardGenLoading').style.display = 'none';
  document.getElementById('step4Content').style.display = 'block';
  updateNextButton();
}

function toggleAdvanced(btn, panelId) {
  const panel = document.getElementById(panelId);
  const isOpen = panel.classList.toggle('open');
  btn.classList.toggle('open', isOpen);
}

function toggleFaq() {
  const el = document.getElementById('faqSection');
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

/* ───────────────────────────────────────────────────────
   마지막 스텝: 지금 발행 / 예약 선택
─────────────────────────────────────────────────────── */
async function chooseNow(el) {
  document.querySelectorAll('#publishChoiceCards .choice-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');

  const result = await publishNow(state.platform);
  if (result && result.success && !result.data?.manual_required) {
    showWizardComplete(`🚀 ${PLATFORM_NAMES[state.platform]}에 발행됐어요!`);
  }
}

function chooseSchedule(el) {
  document.querySelectorAll('#publishChoiceCards .choice-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('scheduleDetail').style.display = 'block';
}

async function handleScheduleClick() {
  const result = await schedulePost();
  if (result && result.success) {
    showWizardComplete(`📅 ${PLATFORM_NAMES[state.platform]} 예약이 완료됐어요!`);
  }
}

function showWizardComplete(message) {
  document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
  document.getElementById('wizardNav').style.display = 'none';
  document.getElementById('wizardBackBtn').style.visibility = 'hidden';
  document.getElementById('completeMessage').textContent = message;
  document.getElementById('wizardComplete').classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function restartWizard() {
  state.platform = 'instagram';
  state.timeline = [];
  state.originalContent = '';
  state.generatedData = null;
  state.selectedBGM = 'none';
  state.customBgmPath = null;
  hasAutoGenerated = false;

  document.querySelectorAll('.platform-tab-row').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-instagram')?.classList.add('active');
  document.getElementById('platformBadge').textContent = PLATFORM_NAMES.instagram;

  document.getElementById('editorArea').value = '';
  document.getElementById('topicInput').value = '';
  document.getElementById('photoDesc').value = '';
  document.getElementById('hashtagArea').style.display = 'none';
  document.getElementById('scheduleDetail').style.display = 'none';
  document.querySelectorAll('#publishChoiceCards .choice-card').forEach(c => c.classList.remove('selected'));
  document.querySelectorAll('.bgm-item').forEach(b => b.classList.remove('selected'));
  document.querySelector('.bgm-item[data-bgm="none"]')?.classList.add('selected');

  renderTimeline();
  updateCharCounter();

  document.getElementById('wizardComplete').classList.remove('active');
  document.getElementById('wizardBackBtn').style.visibility = 'visible';
  goToWizardStep(1);
}

/* ───────────────────────────────────────────────────────
   시작 화면 → 마법사 진입
─────────────────────────────────────────────────────── */
function startWizard() {
  document.getElementById('wizardIntro').classList.remove('active');
  document.getElementById('wizardTopbar').style.display = 'flex';
  goToWizardStep(1);
}

/* ───────────────────────────────────────────────────────
   다크/라이트 모드 전환 (선택은 localStorage에 저장)
─────────────────────────────────────────────────────── */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('autopost_theme', theme); } catch (e) { /* 무시 */ }
  syncThemeToggleIcon();
}

function syncThemeToggleIcon() {
  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  const btn = document.getElementById('themeToggleBtn');
  if (btn) btn.textContent = theme === 'light' ? '🌙' : '☀️';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}
