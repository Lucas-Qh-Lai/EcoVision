 "use strict";
 
 /* ═══════════════════════════════════════════
    EcoVision - 环保之眼 Frontend JS
    中英双语 / Chinese-English Bilingual
    ═══════════════════════════════════════════ */
 
 // ─── i18n ───
 const I18N = {
   zh: {
     appName:'环保之眼', brand:'EcoVision',
     loading:'启动中', ready:'就绪', error:'错误',
     cameraStart:'启动摄像头中...', cameraFail:'无法访问摄像头',
     cameraHint:'将物品放入框内拍照',
     waitingLabel:'等待拍照...', capturing:'识别中...',
     takePhoto:'拍照识别', upload:'上传', photo:'拍照',
     auto:'自动',
     guideTitle:'处理指南',
     recordTitle:'记录', emptyHistory:'暂无记录',
     today:'今日', total:'总计',
     predictFail:'识别失败，请重试',
     modelNotLoaded:'模型未加载，请检查后端',
     unknown:'未知物品',
     category_recyclable:'可回收物', category_hazardous:'有害垃圾',
     category_kitchen:'厨余垃圾', category_other:'其他垃圾',
     stats:'数据统计', back:'返回识别',
     langSwitch:'EN',
     themeToggle:'切换主题',
     hint_default:'将物品放入框内拍照',
     hint_auto:'自动检测中...',
     others:'其他可能',
     possible:'可能的结果',
     fileTooBig:'图片过大，请选择小于10MB的图片',
     decodeFail:'图片处理失败',
   },
   en: {
     appName:'EcoVision', brand:'EcoVision',
     loading:'Starting', ready:'Ready', error:'Error',
     cameraStart:'Starting camera...', cameraFail:'Camera unavailable',
     cameraHint:'Point camera at an item',
     waitingLabel:'Waiting...', capturing:'Classifying...',
     takePhoto:'Capture', upload:'Upload', photo:'Photo',
     auto:'Auto',
     guideTitle:'Disposal Guide',
     recordTitle:'History', emptyHistory:'No records',
     today:'Today', total:'Total',
     predictFail:'Classification failed',
     modelNotLoaded:'Model not loaded. Check backend.',
     unknown:'Unknown item',
     category_recyclable:'Recyclable', category_hazardous:'Hazardous',
     category_kitchen:'Kitchen Waste', category_other:'Other Waste',
     stats:'Stats', back:'Back',
     langSwitch:'中',
     themeToggle:'Toggle theme',
     hint_default:'Point camera at an item',
     hint_auto:'Auto detecting...',
     others:'Other possibilities',
     possible:'Possible results',
     fileTooBig:'Image too large, choose file under 10MB',
     decodeFail:'Image processing failed',
   },
 };
 
 let LANG = 'zh';
 let lang = {};
 function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function t(key) { return lang[key] || key; }
 function setLang(code) {
   LANG = code;
   lang = I18N[code] || I18N.zh;
   try { localStorage.setItem('ecovision-lang', code); } catch(e) {}
   document.documentElement.lang = code === 'zh' ? 'zh-CN' : 'en';
   updateI18nUI();
 }
 
 // ─── State ───
 let videoStream = null;
 let autoInterval = null;
 let isClassifying = false;
 let historyCache = [];
 
 // ─── DOM cache ───
 let DOM = {};
 function cacheDOM() {
   DOM = {
     themeToggle:   document.getElementById('themeToggle'),
     statusDot:     document.getElementById('statusDot'),
     statusText:    document.getElementById('statusText'),
     video:         document.getElementById('video'),
     cameraSection: document.getElementById('cameraSection'),
     cameraHint:    document.getElementById('cameraHint'),
     cameraPlaceholder: document.getElementById('cameraPlaceholder'),
     camStatusText: document.getElementById('camStatusText'),
     videoLabel:    document.getElementById('videoLabel'),
     vlText:        document.querySelector('#videoLabel .vl-text'),
     captureBtn:    document.getElementById('captureBtn'),
     fileInput:     document.getElementById('fileInput'),
     mobileCaptureInput: document.getElementById('mobileCaptureInput'),
     autoToggle:    document.getElementById('autoToggle'),
     resultValue:   document.getElementById('resultValue'),
     categoryBadge: document.getElementById('categoryBadge'),
     confidenceText:document.getElementById('confidenceText'),
     confidenceBar: document.getElementById('confidenceBar'),
     topPredictions:document.getElementById('topPredictions'),
     guideTips:     document.getElementById('guideTips'),
     guideSection:  document.getElementById('guideSection'),
     statToday:     document.getElementById('statToday'),
     statTotal:     document.getElementById('statTotal'),
     historyList:   document.getElementById('historyList'),
     historyCount:  document.getElementById('historyCount'),
     langToggle:    document.getElementById('langToggle'),
   };
 }
 
 // ─── Theme ───
 function initTheme() {
   let theme = 'light';
   try {
     const saved = localStorage.getItem('ecovision-theme');
     if (saved) theme = saved;
     else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) theme = 'dark';
   } catch(e) {}
   document.documentElement.setAttribute('data-theme', theme);
 }
 
 // ─── i18n UI update ───
 function updateI18nUI() {
   document.querySelectorAll('[data-i18n]').forEach(function(el) {
     var key = el.getAttribute('data-i18n');
     if (key && t(key)) {
       el.textContent = t(key);
     }
   });
   if (DOM.langToggle) DOM.langToggle.textContent = t('langSwitch');
   document.title = 'EcoVision - ' + t('appName');
 }
 
 // ─── Status ───
 // ─── Hint ───
 function setHint(text) {
   if (DOM.cameraHint) DOM.cameraHint.textContent = text || '';
 }

 // ─── Status ───
 function setStatus(state, text) {
   var dot = DOM.statusDot, txt = DOM.statusText;
   if (!dot || !txt) return;
   dot.className = 'status-dot ' + state;
   txt.textContent = text || '';
 }
 
 // ─── Camera ───
 async function initCamera() {
   var video = DOM.video, placeholder = DOM.cameraPlaceholder,
       section = DOM.cameraSection, camText = DOM.camStatusText;
   if (!video) return;
 
   var isSecure = window.location.protocol === 'https:' ||
                  window.location.hostname === 'localhost' ||
                  window.location.hostname === '127.0.0.1';
   if (!isSecure) {
     if (camText) camText.textContent = t('cameraFail') + ' (HTTP)';
     setStatus('error', t('cameraFail'));
     return;
   }
 
   if (camText) camText.textContent = t('cameraStart');
 
   try {
     var stream = await navigator.mediaDevices.getUserMedia({
       video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
       audio: false,
     });
     videoStream = stream;
     video.srcObject = stream;
     await video.play();
     if (section) section.classList.add('ready');
     setHint(t('hint_default'));
   setStatus('active', t('ready'));
   } catch (err) {
     console.error('[ecovision] Camera error:', err);
     if (camText) camText.textContent = t('cameraFail');
     if (section) section.classList.add('ready');
     setHint(t('cameraFail'));
     setStatus('inactive', t('cameraFail'));
   }
 }
 
 // ─── Capture → Predict ───
 async function captureAndPredict(source) {
   if (isClassifying) return;
   isClassifying = true;
   if (DOM.captureBtn) DOM.captureBtn.disabled = true;
   setStatus('processing', t('capturing'));
   if (DOM.vlText) DOM.vlText.textContent = t('capturing');
   if (DOM.videoLabel) DOM.videoLabel.style.opacity = '1';
   if (DOM.videoLabel) DOM.videoLabel.style.transform = 'translateY(0)';
 
   try {
     var imageData;
 
     if (source === 'video') {
       var canvas = document.createElement('canvas');
       var vw = DOM.video.videoWidth || 640;
       var vh = DOM.video.videoHeight || 480;
       canvas.width = vw;
       canvas.height = vh;
       var ctx = canvas.getContext('2d');
       ctx.drawImage(DOM.video, 0, 0, vw, vh);
       imageData = canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
     } else if (typeof source === 'string' && source.length > 0) {
       imageData = source;
     }
 
     if (!imageData) {
       throw new Error('No image data');
     }
 
     var res = await fetch('/api/predict', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ image: imageData }),
     });
 
     if (!res.ok) {
       var errBody = await res.text();
       throw new Error(errBody || 'HTTP ' + res.status);
     }
 
     var data = await res.json();
 
     if (data.success && data.label) {
       renderResult(data);
       if ((data.confidence || 0) >= 50) {
         addHistory(data);
         addCount();
       }
     } else {
       showError(data.message || t('predictFail'));
     }
   } catch (err) {
     console.error('[ecovision] Predict error:', err);
     if (err.message && err.message.indexOf('模型未加载') !== -1) {
       showError(t('modelNotLoaded'));
     } else {
       showError(t('predictFail'));
     }
   } finally {
     isClassifying = false;
     if (DOM.captureBtn) DOM.captureBtn.disabled = false;
     setStatus('active', t('ready'));
     if (DOM.vlText) DOM.vlText.textContent = t('waitingLabel');
     // Re-schedule auto capture after completion
     if (DOM.autoToggle && DOM.autoToggle.checked) {
       scheduleAutoCapture();
     }
   }
 }

 function scheduleAutoCapture() {
   var toggle = DOM.autoToggle;
   if (!toggle || !toggle.checked) return;
   if (isClassifying) {
     autoInterval = setTimeout(scheduleAutoCapture, 500);
     return;
   }
   autoInterval = setTimeout(function() { captureAndPredict('video'); }, 3000);
 }
 
 // ─── Render Result ───
function renderResult(data) {
  var conf = data.confidence || 0;
  var isHighConf = conf >= 50;
  var rootStyle = getComputedStyle(document.documentElement);
  var warnClr = rootStyle.getPropertyValue('--warning').trim() || '#F59E0B';
  var dngrClr = rootStyle.getPropertyValue('--danger').trim() || '#EF4444';
  var accClr = rootStyle.getPropertyValue('--accent').trim() || '#059669';

  var badge = DOM.categoryBadge;
  if (badge) {
    var catIcon = (data.category_info && data.category_info.icon) || '\uD83D\uDDD1\uFE0F';
    if (isHighConf) {
      var catColor = (data.category_info && data.category_info.color) || '#6B7280';
      var catName = data.category || t('unknown');
      badge.textContent = catIcon + ' ' + catName;
      badge.style.background = catColor;
    } else {
      badge.textContent = '\u26A0 ' + t('unknown');
      badge.style.background = warnClr;
    }
  }

  var val = DOM.resultValue;
  if (val) {
    if (isHighConf) {
      val.textContent = data.display_name || data.label || t('unknown');
      val.classList.remove('uncertain-label');
    } else {
      val.innerHTML = '';
      var span = document.createElement('span');
      span.className = 'uncertain-label';
      span.textContent = t('unknown');
      val.appendChild(span);
    }
  }

  var confTextEl = DOM.confidenceText;
  if (confTextEl) confTextEl.textContent = conf.toFixed(1) + '%';

  var bar = DOM.confidenceBar;
  if (bar) {
    bar.style.width = Math.min(conf, 100) + '%';
    bar.style.background = isHighConf ? accClr : warnClr;
  }

  var topDiv = DOM.topPredictions;
  if (topDiv && data.top_predictions) {
    var preds = data.top_predictions;
    if (isHighConf) {
      // Show "other possibilities" below top result
      var others = preds.slice(1).filter(function(p) { return (p.score || 0) > 5; });
      if (others.length > 0) {
        topDiv.innerHTML = '<div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:4px;">' + t('others') + '</div>' +
          '<div class="top-predictions-list">' +
          others.slice(0, 4).map(function(p) {
            var pct = Math.min(p.score || 0, 100);
            return '<div class="pred-item">' +
              '<span class="pred-name">' + escapeHtml(p.display_name || p.label) + '</span>' +
              '<div class="pred-bar-wrap"><div class="pred-bar" style="width:' + pct + '%"></div></div>' +
              '<span class="pred-score">' + pct.toFixed(1) + '%</span></div>';
          }).join('') + '</div>';
      } else {
        topDiv.innerHTML = '';
      }
    } else {
      // Low confidence: show all top results as "possible"
      topDiv.innerHTML = '<div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:4px;">' + t('possible') + '</div>' +
        '<div class="top-predictions-list">' +
        preds.slice(0, 5).map(function(p) {
          var pct = Math.min(p.score || 0, 100);
          return '<div class="pred-item">' +
            '<span class="pred-name">' + escapeHtml(p.display_name || p.label) + '</span>' +
            '<div class="pred-bar-wrap"><div class="pred-bar" style="width:' + pct + '%"></div></div>' +
            '<span class="pred-score">' + pct.toFixed(1) + '%</span></div>';
        }).join('') + '</div>';
    }
  }

  var tipsList = DOM.guideTips;
  if (tipsList && data.guide && data.guide.tips) {
    tipsList.innerHTML = data.guide.tips.map(function(tip) {
      return '<li>' + escapeHtml(tip) + '</li>';
    }).join('');
    if (DOM.guideSection) DOM.guideSection.classList.add('has-content');
  } else if (tipsList) {
    tipsList.innerHTML = '';
  }

  var vlText = DOM.vlText;
  if (vlText) vlText.textContent = data.display_name || data.label || '';
  var oldConf = document.querySelector('#videoLabel .vl-conf');
  if (oldConf) oldConf.remove();
  var vl = DOM.videoLabel;
  if (vl && data.confidence !== undefined) {
    var cs = document.createElement('span');
    cs.className = 'vl-conf';
    cs.textContent = data.confidence.toFixed(1) + '%';
    vl.appendChild(cs);
  }
}

function showError(msg) {
   var dngrClr = getComputedStyle(document.documentElement).getPropertyValue('--danger').trim() || '#EF4444';
   var badge = DOM.categoryBadge;
   if (badge) { badge.textContent = '⚠ ' + msg; badge.style.background = dngrClr; }
   var val = DOM.resultValue;
   if (val) val.textContent = '';
   var bar = DOM.confidenceBar;
   if (bar) bar.style.width = '0%';
   if (DOM.topPredictions) DOM.topPredictions.innerHTML = '';
   if (DOM.guideTips) DOM.guideTips.innerHTML = '';
   if (DOM.vlText) DOM.vlText.textContent = msg;
 }
 
 // ─── History (localStorage) ───
 var HISTORY_KEY = 'ecovision-history';
 var MAX_HISTORY = 50;
 
 function loadHistory() {
   try {
     var raw = localStorage.getItem(HISTORY_KEY);
     historyCache = raw ? JSON.parse(raw) : [];
     if (!Array.isArray(historyCache)) historyCache = [];
   } catch(e) { historyCache = []; }
   renderHistory();
 }
 
 function addHistory(data) {
   var entry = {
     label: data.label,
     display_name: data.display_name || data.label,
     category: data.category || '',
     icon: (data.category_info && data.category_info.icon) || '🗑️',
     color: (data.category_info && data.category_info.color) || '#6B7280',
     confidence: data.confidence || 0,
     time: new Date().toLocaleTimeString(),
   };
   historyCache.unshift(entry);
   if (historyCache.length > MAX_HISTORY) historyCache.length = MAX_HISTORY;
   try { localStorage.setItem(HISTORY_KEY, JSON.stringify(historyCache)); } catch(e) {}
   renderHistory();
 }
 
 function renderHistory() {
   var list = DOM.historyList;
   var count = DOM.historyCount;
   if (!list) return;
   if (historyCache.length === 0) {
     list.innerHTML = '<div class="history-empty">' + t('emptyHistory') + '</div>';
     if (count) count.textContent = '0';
     return;
   }
   list.innerHTML = historyCache.map(function(h) {
     return '<div class="history-item">' +
       '<div class="h-icon" style="background:' + (h.color || '#6B7280') + '22;color:' + (h.color || '#6B7280') + '">' + (h.icon || '🗑️') + '</div>' +
       '<div class="h-info">' +
         '<div class="h-name">' + (h.display_name || h.label) + '</div>' +
         '<div class="h-time">' + (h.time || '') + '</div>' +
       '</div>' +
     '</div>';
   }).join('');
   if (count) count.textContent = historyCache.length;
 }
 
 // ─── Today Stats ───
 var _todayCount = 0;
 var _totalCount = 0;
 
 function addCount() {
   _todayCount++;
   _totalCount++;
   if (DOM.statToday) DOM.statToday.textContent = _todayCount;
   if (DOM.statTotal) DOM.statTotal.textContent = _totalCount;
 }
 
 async function updateStats() {
   try {
     var res = await fetch('/api/stats?days=1');
     var data = await res.json();
     _todayCount = data.total || 0;
     if (DOM.statToday) DOM.statToday.textContent = _todayCount;
     var res7 = await fetch('/api/stats?days=365');
     var data7 = await res7.json();
     _totalCount = data7.total || 0;
     if (DOM.statTotal) DOM.statTotal.textContent = _totalCount;
   } catch(e) {}
 }
 
 // ─── File Upload Handler ───
 function handleFileUpload(file) {
   if (!file) return;
   if (file.size > 10 * 1024 * 1024) {
     if (DOM.resultValue) DOM.resultValue.textContent = t('fileTooBig');
     return;
   }
   var reader = new FileReader();
   reader.onload = function(e) {
     var b64 = e.target.result.split(',')[1];
     if (!b64) { if (DOM.resultValue) DOM.resultValue.textContent = t('decodeFail'); return; }
     captureAndPredict(b64);
   };
   reader.readAsDataURL(file);
 }
 
 // ─── Event Listeners ───
 function setupEventListeners() {
   if (DOM.themeToggle) {
     DOM.themeToggle.addEventListener('click', function() {
       var h = document.documentElement;
       var n = h.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
       h.setAttribute('data-theme', n);
       try { localStorage.setItem('ecovision-theme', n); } catch(e) {}
     });
   }
 
   if (DOM.captureBtn) {
     DOM.captureBtn.addEventListener('click', function() { captureAndPredict('video'); });
   }
 
   if (DOM.fileInput) {
     DOM.fileInput.addEventListener('change', function() {
       if (this.files && this.files[0]) handleFileUpload(this.files[0]);
       this.value = '';
     });
   }
 
   if (DOM.mobileCaptureInput) {
     DOM.mobileCaptureInput.addEventListener('change', function() {
       if (this.files && this.files[0]) handleFileUpload(this.files[0]);
       this.value = '';
     });
   }
 
   if (DOM.autoToggle) {
     DOM.autoToggle.addEventListener('change', function() {
       if (this.checked) {
         setHint(t('hint_auto'));
         scheduleAutoCapture();
       } else {
         if (autoInterval) { clearTimeout(autoInterval); autoInterval = null; }
         setHint(t('hint_default'));
       }
     });
   }
 
   if (DOM.langToggle) {
     DOM.langToggle.addEventListener('click', function() {
       setLang(LANG === 'zh' ? 'en' : 'zh');
     });
   }
 }
 
 // ─── Cleanup ───
 window.addEventListener('beforeunload', function() {
   if (autoInterval) { clearTimeout(autoInterval); autoInterval = null; }
   if (videoStream) { videoStream.getTracks().forEach(function(t) { t.stop(); }); videoStream = null; }
 });

 // ─── Init ───
 async function init() {
   cacheDOM();
 
   var savedLang = 'zh';
   try { var s = localStorage.getItem('ecovision-lang'); if (s && I18N[s]) savedLang = s; } catch(e) {}
   setLang(savedLang);
 
   initTheme();
 
   if (DOM.themeToggle) {
     var newToggle = DOM.themeToggle.cloneNode(true);
     if (DOM.themeToggle.parentNode) DOM.themeToggle.parentNode.replaceChild(newToggle, DOM.themeToggle);
     DOM.themeToggle = newToggle;
   }
 
   setupEventListeners();
   loadHistory();
   await initCamera();
   updateStats();
   setInterval(updateStats, 30000);
   setHint(t('hint_default'));
   setStatus('active', t('ready'));
   console.log('[ecovision] EcoVision initialized');
 }
 
 document.addEventListener('DOMContentLoaded', init);
