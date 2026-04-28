/* ── Main JS ── */

// Sidebar toggle
document.addEventListener('DOMContentLoaded', function () {
    const toggleBtn = document.getElementById('toggleSidebar');
    const body = document.body;

    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            body.classList.toggle('sidebar-collapsed');
        });
    }

    // Live clock
    const clockEl = document.getElementById('currentDateTime');
    function updateClock() {
        if (!clockEl) return;
        const now = new Date();
        clockEl.textContent = now.toLocaleDateString('en-PH', {
            weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }
    updateClock();
    setInterval(updateClock, 60000);

    // Theme logic
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
        // Initial icon update (theme is already set by inline script in head)
        updateThemeIcon(document.documentElement.getAttribute('data-theme'));

        themeBtn.addEventListener('click', () => {
            let current = document.documentElement.getAttribute('data-theme');
            let next = (current === 'light') ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', next);
            document.documentElement.setAttribute('data-bs-theme', next);
            localStorage.setItem('app_theme', next);
            updateThemeIcon(next);
        });
    }

    function updateThemeIcon(theme) {
        const icon = themeBtn.querySelector('i');
        if (theme === 'light') {
            icon.className = 'bi bi-moon-stars-fill'; // show moon when light
            themeBtn.setAttribute('title', 'Switch to Dark Mode');
        } else {
            icon.className = 'bi bi-brightness-high-fill'; // show sun when dark
            themeBtn.setAttribute('title', 'Switch to Light Mode');
        }
    }

    // Auto-dismiss alerts after 5s
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(el => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
            bsAlert.close();
        });
    }, 5000);

    // Tank selection grid
    document.querySelectorAll('.tank-item').forEach(item => {
        item.addEventListener('click', function () {
            const cb = this.querySelector('input[type="checkbox"]');
            if (cb) {
                cb.checked = !cb.checked;
                this.classList.toggle('selected', cb.checked);
                updateTankCount();
            }
        });
    });

    // Select All tanks button
    const selectAllBtn = document.getElementById('selectAllTanks');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const allItems = document.querySelectorAll('.tank-item');
            const allChecked = [...allItems].every(i => i.querySelector('input[type="checkbox"]').checked);
            allItems.forEach(item => {
                const cb = item.querySelector('input[type="checkbox"]');
                if (cb) { cb.checked = !allChecked; item.classList.toggle('selected', !allChecked); }
            });
            updateTankCount();
        });
    }

    function updateTankCount() {
        const countEl = document.getElementById('selectedTankCount');
        if (!countEl) return;
        const count = document.querySelectorAll('.tank-item input[type="checkbox"]:checked').length;
        countEl.textContent = `${count} tank(s) selected`;
    }

    // Init DataTables
    if (typeof $.fn.DataTable !== 'undefined') {
        $('.data-table').DataTable({
            responsive: true,
            pageLength: 20,
            language: { search: '', searchPlaceholder: 'Search...' },
        });
    }
});

// Consumer tank loader for return form
function loadConsumerTanks(consumerId) {
    if (!consumerId) return;
    fetch(`/transactions/api/consumer-tanks/${consumerId}`)
        .then(r => r.json())
        .then(tanks => {
            const grid = document.getElementById('tankGrid');
            if (!grid) return;
            grid.innerHTML = '';
            if (tanks.length === 0) {
                grid.innerHTML = '<p class="text-muted" style="grid-column:1/-1">No tanks currently with this consumer.</p>';
                return;
            }
            tanks.forEach(t => {
                grid.innerHTML += `
                <div class="tank-item" onclick="toggleTank(this)">
                    <input type="checkbox" name="tank_ids" value="${t.id}">
                    <div class="tank-sn">${t.serial_number}</div>
                    <div class="tank-size">${t.tank_size}</div>
                    <div class="mt-1">
                        <select class="form-select form-select-sm" name="condition_${t.id}" onclick="event.stopPropagation()">
                            <option value="Good">Good</option>
                            <option value="Damaged">Damaged</option>
                        </select>
                    </div>
                </div>`;
            });
        });
}

function toggleTank(el) {
    const cb = el.querySelector('input[type="checkbox"]');
    if (cb) {
        cb.checked = !cb.checked;
        el.classList.toggle('selected', cb.checked);
    }
}
