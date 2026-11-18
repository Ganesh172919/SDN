/**
 * repo_explorer.js - Interactive Repository & Codebase Explorer
 * Displays the complete file tree of the SELF-X repository, allows live file inspection,
 * and provides step-by-step multi-platform installation guides (Linux, Mac, Windows).
 * Course: EC466 Software Defined Networks · Team SDN_07 · IIIT Dharwad
 */

(function () {
  'use strict';

  let repoFiles = [];
  let activeFilter = 'all';
  let activeFilePath = 'README.md';

  async function loadRepoTree() {
    const listEl = document.getElementById('repoFileListContainer');
    const filesStatEl = document.getElementById('repoStatFiles');
    const linesStatEl = document.getElementById('repoStatLines');
    const sizeStatEl = document.getElementById('repoStatSize');

    if (listEl) {
      listEl.innerHTML = '<div style="color:#0284c7; padding:12px; font-size:0.85rem; text-align:center;">Scanning repository files...</div>';
    }

    try {
      const res = await fetch('/api/repo/tree');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      repoFiles = data.files || [];

      if (filesStatEl) filesStatEl.textContent = `${data.total_files || repoFiles.length} files`;
      if (linesStatEl) linesStatEl.textContent = `${(data.total_lines_of_code || 0).toLocaleString()} lines`;
      if (sizeStatEl) {
        const mb = ((data.total_size_bytes || 0) / (1024 * 1024)).toFixed(1);
        sizeStatEl.textContent = `${mb} MB`;
      }

      renderFileList();

      // Automatically load README.md or the first file
      const defaultFile = repoFiles.find(f => f.path === 'README.md') || repoFiles[0];
      if (defaultFile) {
        loadFileContent(defaultFile.path);
      }
    } catch (err) {
      if (listEl) {
        listEl.innerHTML = `<div style="color:#ef4444; padding:12px; font-size:0.85rem;">Error loading repository tree: ${err.message}</div>`;
      }
    }
  }

  function getFileIcon(ext) {
    switch (ext) {
      case '.py': return '🐍';
      case '.tex':
      case '.bib': return '📜';
      case '.js': return '⚡';
      case '.html': return '🌐';
      case '.css': return '🎨';
      case '.json': return '📋';
      case '.md': return '📝';
      case '.pdf': return '📕';
      case '.zip': return '📦';
      case '.png':
      case '.jpg': return '🖼️';
      case '.sh':
      case '.bat':
      case '.ps1': return '⚙️';
      default: return '📄';
    }
  }

  function renderFileList() {
    const listEl = document.getElementById('repoFileListContainer');
    if (!listEl) return;

    const searchTerm = (document.getElementById('repoSearchInput')?.value || '').toLowerCase().trim();

    const filtered = repoFiles.filter(f => {
      // Category filter
      if (activeFilter !== 'all') {
        if (!f.path.toLowerCase().startsWith(activeFilter.toLowerCase())) {
          return false;
        }
      }
      // Search term filter
      if (searchTerm) {
        return f.path.toLowerCase().includes(searchTerm) || f.name.toLowerCase().includes(searchTerm);
      }
      return true;
    });

    if (filtered.length === 0) {
      listEl.innerHTML = '<div style="color:#64748b; font-size:0.82rem; padding:12px; text-align:center;">No matching files found.</div>';
      return;
    }

    const MAX_VISIBLE = 100;
    const visibleFiles = filtered.slice(0, MAX_VISIBLE);

    let html = visibleFiles.map(f => {
      const isSelected = f.path === activeFilePath;
      const icon = getFileIcon(f.extension);
      const sizeStr = f.size > 1048576 
        ? `${(f.size / 1048576).toFixed(1)} MB` 
        : `${Math.round(f.size / 1024) || 1} KB`;
      const linesStr = f.lines ? `${f.lines} lines` : '';

      return `
        <div class="repo-file-item ${isSelected ? 'selected' : ''}" data-path="${f.path}" 
             style="display:flex; align-items:center; justify-content:space-between; padding:6px 8px; margin-bottom:2px; border-radius:4px; cursor:pointer; font-size:0.8rem; background:${isSelected ? '#e0f2fe' : '#ffffff'}; border:1px solid ${isSelected ? '#0284c7' : '#e2e8f0'}; transition:background 0.15s ease;">
          <div style="display:flex; align-items:center; gap:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            <span style="font-size:0.95rem;">${icon}</span>
            <span style="font-family:'JetBrains Mono',monospace; color:#0f172a; font-weight:${isSelected ? '700' : '500'}; overflow:hidden; text-overflow:ellipsis;">${f.path}</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
            ${linesStr ? `<span style="font-size:0.7rem; color:#64748b;">${linesStr}</span>` : ''}
            <span style="font-size:0.7rem; color:#0369a1; font-weight:600; background:#f0f9ff; padding:1px 5px; border-radius:3px;">${sizeStr}</span>
          </div>
        </div>
      `;
    }).join('');

    if (filtered.length > MAX_VISIBLE) {
      html += `
        <div style="text-align:center; padding:10px 8px; font-size:0.78rem; color:#334155; font-weight:600; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:4px; margin-top:6px;">
          Showing first ${MAX_VISIBLE} of ${filtered.length.toLocaleString()} matching files. Filter by folder (paper/, selfx/, Web/) or use the search bar above to inspect specific files instantly.
        </div>
      `;
    }

    listEl.innerHTML = html;

    // Attach click listeners to all items
    listEl.querySelectorAll('.repo-file-item').forEach(el => {
      el.addEventListener('click', () => {
        const path = el.getAttribute('data-path');
        if (path) {
          activeFilePath = path;
          renderFileList();
          loadFileContent(path);
        }
      });
    });
  }

  async function loadFileContent(filePath) {
    const pathEl = document.getElementById('repoSelectedFilePath');
    const iconEl = document.getElementById('repoSelectedFileIcon');
    const linesEl = document.getElementById('repoSelectedFileLines');
    const sizeEl = document.getElementById('repoSelectedFileSize');
    const shaEl = document.getElementById('repoSelectedFileSha');
    const codeEl = document.getElementById('repoFileContentCode');

    if (pathEl) pathEl.textContent = filePath;
    const ext = '.' + filePath.split('.').pop().toLowerCase();
    if (iconEl) iconEl.textContent = getFileIcon(ext);

    if (codeEl) {
      codeEl.textContent = 'Loading file contents from active workspace...';
    }

    try {
      const res = await fetch(`/api/repo/file?path=${encodeURIComponent(filePath)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (linesEl) {
        linesEl.textContent = data.is_binary ? 'Binary File' : `${data.lines || 0} lines`;
      }
      if (sizeEl) {
        const sizeStr = data.size > 1048576 
          ? `${(data.size / 1048576).toFixed(2)} MB` 
          : `${(data.size / 1024).toFixed(1)} KB`;
        sizeEl.textContent = sizeStr;
      }
      if (shaEl) {
        shaEl.textContent = data.sha256 ? `SHA: ${data.sha256.substring(0, 16)}...` : 'Binary Asset';
      }

      if (codeEl) {
        if (data.is_binary) {
          codeEl.textContent = `[Binary Asset: ${filePath}]\nSize: ${data.size.toLocaleString()} bytes\n\nThis file is verified in the repository distribution.` +
            (data.download_url ? `\nDirect Download: ${window.location.origin}${data.download_url}` : '');
        } else {
          codeEl.textContent = data.content || '(Empty file)';
        }
      }
    } catch (err) {
      if (codeEl) {
        codeEl.textContent = `Error loading file ${filePath}: ${err.message}`;
      }
    }
  }

  function initSubtabs() {
    const btnExplorer = document.getElementById('btnSubtabRepoExplorer');
    const btnGuide = document.getElementById('btnSubtabMultiOSGuide');
    const panelExplorer = document.getElementById('panelRepoExplorerView');
    const panelGuide = document.getElementById('panelMultiOSGuideView');

    if (btnExplorer && btnGuide && panelExplorer && panelGuide) {
      btnExplorer.addEventListener('click', () => {
        btnExplorer.classList.add('active');
        btnGuide.classList.remove('active');
        panelExplorer.style.display = 'block';
        panelGuide.style.display = 'none';
      });

      btnGuide.addEventListener('click', () => {
        btnGuide.classList.add('active');
        btnExplorer.classList.remove('active');
        panelExplorer.style.display = 'none';
        panelGuide.style.display = 'block';
      });
    }
  }

  function initFilters() {
    const searchInput = document.getElementById('repoSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        renderFileList();
      });
    }

    document.querySelectorAll('.repo-filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.repo-filter-pill').forEach(b => {
          b.classList.remove('active');
          b.style.background = '';
          b.style.color = '';
        });
        btn.classList.add('active');
        btn.style.background = '#0284c7';
        btn.style.color = '#ffffff';
        activeFilter = btn.getAttribute('data-filter') || 'all';
        renderFileList();
      });
    });

    const btnRefresh = document.getElementById('btnRefreshRepoTree');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        loadRepoTree();
      });
    }

    const btnCopy = document.getElementById('btnCopyRepoFileContent');
    if (btnCopy) {
      btnCopy.addEventListener('click', () => {
        const codeEl = document.getElementById('repoFileContentCode');
        if (codeEl && codeEl.textContent) {
          navigator.clipboard.writeText(codeEl.textContent).then(() => {
            const original = btnCopy.textContent;
            btnCopy.textContent = '✓ Copied!';
            setTimeout(() => { btnCopy.textContent = original; }, 1800);
          });
        }
      });
    }
  }

  function init() {
    initSubtabs();
    initFilters();
    loadRepoTree();
  }

  window.RepoExplorer = {
    init,
    loadRepoTree,
    loadFileContent
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
