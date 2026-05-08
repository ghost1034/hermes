document.addEventListener('DOMContentLoaded', async () => {
    function escapeHtml(unsafe) {
        return (unsafe ?? '').toString()
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
    const sidebar = document.getElementById('sidebar-content');
    const viewerContainer = document.getElementById('viewer-container');
    const viewerTitle = document.getElementById('viewer-title');
    const downloadBtn = document.getElementById('download-btn');

    try {
        const response = await fetch('pipelines/manifest.json');
        if (!response.ok) throw new Error('Manifest not found');
        const manifest = await response.json();
        
        sidebar.innerHTML = '';
        
        for (const [pipeline, files] of Object.entries(manifest)) {
            const section = document.createElement('div');
            section.className = 'mb-4';
            section.innerHTML = `<h3 class="font-semibold text-gray-700 uppercase text-xs mb-2 tracking-wider">${escapeHtml(pipeline)}</h3>`;
            
            const ul = document.createElement('ul');
            ul.className = 'space-y-1';
            
            files.forEach(file => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.href = '#';
                a.className = 'block px-2 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded truncate transition-colors';
                a.textContent = file.name;
                a.title = file.name;
                a.onclick = (e) => {
                    e.preventDefault();
                    document.querySelectorAll('#sidebar-content a').forEach(el => el.classList.remove('bg-blue-100', 'font-medium'));
                    a.classList.add('bg-blue-100', 'font-medium');
                    loadFile(file);
                };
                li.appendChild(a);
                ul.appendChild(li);
            });
            
            section.appendChild(ul);
            sidebar.appendChild(section);
        }
    } catch (error) {
        sidebar.innerHTML = `<p class="text-red-500 text-sm">Failed to load pipelines: ${escapeHtml(error.message)}</p>`;
    }

    async function loadFile(file) {
        viewerTitle.textContent = file.path;
        viewerContainer.innerHTML = '<p class="text-gray-500 animate-pulse">Loading content...</p>';
        downloadBtn.classList.add('hidden');
        
        try {
            const normalizedPath = (file.path || '').trim().toLowerCase();
            if (normalizedPath.startsWith('javascript:') || normalizedPath.startsWith('data:')) {
                throw new Error('Invalid file path');
            }
            
            downloadBtn.href = file.path;
            downloadBtn.classList.remove('hidden');

            const response = await fetch(file.path);
            if (!response.ok) throw new Error('Failed to fetch file');
            const content = await response.text();
            
            if (file.type === '.md') {
                viewerContainer.innerHTML = `<div class="prose max-w-none bg-white p-8 rounded shadow-sm">${DOMPurify.sanitize(marked.parse(content))}</div>`;
            } else if (file.type === '.csv') {
                const parsed = Papa.parse(content, { header: true, skipEmptyLines: true });
                let tableHtml = '<div class="overflow-x-auto bg-white rounded shadow-sm border border-gray-200"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr>';
                if (parsed.meta.fields && parsed.meta.fields.length > 0) {
                    parsed.meta.fields.forEach(field => {
                        tableHtml += `<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${escapeHtml(field)}</th>`;
                    });
                    tableHtml += '</tr></thead><tbody class="bg-white divide-y divide-gray-200">';
                    parsed.data.forEach(row => {
                        tableHtml += '<tr class="hover:bg-gray-50 transition-colors">';
                        parsed.meta.fields.forEach(field => {
                            tableHtml += `<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${escapeHtml(row[field] !== undefined ? row[field] : '')}</td>`;
                        });
                        tableHtml += '</tr>';
                    });
                } else {
                     tableHtml += '</tr></thead><tbody><tr><td class="p-6 text-sm text-gray-500">Could not parse CSV fields</td></tr>';
                }
                tableHtml += '</tbody></table></div>';
                viewerContainer.innerHTML = tableHtml;
            } else if (file.type === '.json') {
                try {
                    const parsed = JSON.parse(content);
                    const pre = document.createElement('pre');
                    pre.className = 'bg-gray-900 text-gray-100 p-6 rounded overflow-auto shadow-sm text-sm font-mono leading-relaxed';
                    const code = document.createElement('code');
                    code.textContent = JSON.stringify(parsed, null, 2);
                    pre.appendChild(code);
                    viewerContainer.innerHTML = '';
                    viewerContainer.appendChild(pre);
                } catch {
                    // Fallback to text if malformed
                    const pre = document.createElement('pre');
                    pre.className = 'bg-white text-gray-800 p-6 rounded overflow-auto shadow-sm border text-sm font-mono leading-relaxed';
                    pre.textContent = content;
                    viewerContainer.innerHTML = '';
                    viewerContainer.appendChild(pre);
                }
            } else {
                const pre = document.createElement('pre');
                pre.className = 'bg-white text-gray-800 p-6 rounded overflow-auto shadow-sm border border-gray-200 text-sm font-mono leading-relaxed whitespace-pre-wrap';
                pre.textContent = content;
                viewerContainer.innerHTML = '';
                viewerContainer.appendChild(pre);
            }
        } catch (error) {
            viewerContainer.innerHTML = `<div class="bg-red-50 text-red-700 p-4 rounded border border-red-200"><strong class="font-bold">Error rendering file:</strong> ${escapeHtml(error.message)}</div>`;
        }
    }
});